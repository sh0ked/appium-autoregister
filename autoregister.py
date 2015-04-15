# coding: utf-8
import argparse
import logging
logging.basicConfig(level=logging.DEBUG)
import tempfile
import os
import socket
from subprocess import Popen
from string import Template

from android import android_devices


nodes = list()

config_template = Template("""
{
    "capabilities": [{
        "browserName": "$browserName",
        "version": "$version",
        "maxInstances": 1,
        "platformName": "$platform",
        "deviceName": "$device"
    }],
    "configuration": {
        "cleanUpCycle": 2000,
        "timeout": 30000,
        "proxy": "org.openqa.grid.selenium.proxy.DefaultRemoteProxy",
        "url": "http://$appium_host:$appium_port/wd/hub",
        "host": "$appium_host",
        "port": $appium_port,
        "maxSession": 1,
        "register": true,
        "registerCycle": 5000,
        "hubPort": $grid_port,
        "hubHost": "$grid_host"
    }
}
""")


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class AppiumNode(object):
    appium_executable = os.environ.get("APPIUM_EXECUTABLE", None)
    if appium_executable is None:
        exit('set $APPIUM_EXECUTABLE to path of appium executable')

    def __init__(self, port, device, config_file):
        self.port = port
        self.device = device
        self.config_file = config_file
        self.process = None

    def start(self):
        if self.process is not None:
            return self.process

        logging.info("starting appium node for %s" % self.device)
        command = [
            self.appium_executable,
            "--nodeconfig", self.config_file,
            "--port", str(self.port),
            "--bootstrap-port", str(get_free_port()),
            "--udid", self.device.name]
        logging.info("running command %s" % " ".join(command))
        self.process = Popen(command)
        logging.info("process started with pid %s" % self.process.pid)
        return self.process

    def stop(self):
        self.process.kill()
        try:
            os.remove(self.config_file)
        except FileNotFoundError:
            # file already deleted
            pass
        logging.info("appium node for %s stopped" % self.device)


def register(grid_host, grid_port, appium_host):
    global nodes

    already_handled_devices = {node.device.name: node for node in nodes}
    for device in android_devices():
        if device.name in already_handled_devices.keys():
            del already_handled_devices[device.name]
            continue

        config_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        port = get_free_port()
        config = generate_config(device, port, grid_host, grid_port, appium_host)
        config_file.write(config)
        config_file.flush()
        node = AppiumNode(port, device, config_file.name)
        node.start()
        nodes.append(node)

    for node in already_handled_devices.values():
        node.stop()
        nodes.remove(node)


def generate_config(device, appium_port, grid_host, grid_port, appium_host):
    return config_template.substitute({
        "browserName": device.model,
        "version": device.version,
        "platform": device.platform,
        "device": device.name,
        "appium_host": appium_host,
        "appium_port": appium_port,
        "grid_host": grid_host,
        "grid_port": grid_port,
    })


def main(grid_host, grid_port, appium_host):
    logging.info("start registring devices...")
    try:
        while True:
            register(grid_host, grid_port, appium_host)
    except KeyboardInterrupt:
        logging.info("stopping")
        for node in nodes:
            node.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run appium autoregister')
    parser.add_argument('--grid-host', type=str, dest='grid_host', default="localhost",
                        help='Selenium grid host register to. Default localhost.')
    parser.add_argument('--grid-post', type=int, dest='grid_port', default=4444,
                        help='Selenium grid port register to. Default 4444.')
    parser.add_argument('--appium-host', type=str, dest='appium_host', default="localhost",
                        help='This machine host, to be discovered from grid. Default localhost.')
    args = parser.parse_args()
    main(args.grid_host, args.grid_port, args.appium_host)
