# Open mode AP tests
# Copyright (c) 2014, Qualcomm Atheros, Inc.
#
# This software may be distributed under the terms of the BSD license.
# See README for more details.

import logging
logger = logging.getLogger()
import struct
import subprocess
import time

import hostapd
import hwsim_utils
from utils import alloc_fail
from wpasupplicant import WpaSupplicant

def test_ap_open(dev, apdev):
    """AP with open mode (no security) configuration"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bg_scan_period="0")
    ev = hapd.wait_event([ "AP-STA-CONNECTED" ], timeout=5)
    if ev is None:
        raise Exception("No connection event received from hostapd")
    hwsim_utils.test_connectivity(dev[0], hapd)

    dev[0].request("DISCONNECT")
    ev = hapd.wait_event([ "AP-STA-DISCONNECTED" ], timeout=5)
    if ev is None:
        raise Exception("No disconnection event received from hostapd")

def test_ap_open_packet_loss(dev, apdev):
    """AP with open mode configuration and large packet loss"""
    params = { "ssid": "open",
               "ignore_probe_probability": "0.5",
               "ignore_auth_probability": "0.5",
               "ignore_assoc_probability": "0.5",
               "ignore_reassoc_probability": "0.5" }
    hapd = hostapd.add_ap(apdev[0]['ifname'], params)
    for i in range(0, 3):
        dev[i].connect("open", key_mgmt="NONE", scan_freq="2412",
                       wait_connect=False)
    for i in range(0, 3):
        dev[i].wait_connected(timeout=20)

def test_ap_open_unknown_action(dev, apdev):
    """AP with open mode configuration and unknown Action frame"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412")
    bssid = apdev[0]['bssid']
    cmd = "MGMT_TX {} {} freq=2412 action=765432".format(bssid, bssid)
    if "FAIL" in dev[0].request(cmd):
        raise Exception("Could not send test Action frame")
    ev = dev[0].wait_event(["MGMT-TX-STATUS"], timeout=10)
    if ev is None:
        raise Exception("Timeout on MGMT-TX-STATUS")
    if "result=SUCCESS" not in ev:
        raise Exception("AP did not ack Action frame")

def test_ap_open_reconnect_on_inactivity_disconnect(dev, apdev):
    """Reconnect to open mode AP after inactivity related disconnection"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412")
    hapd.request("DEAUTHENTICATE " + dev[0].p2p_interface_addr() + " reason=4")
    dev[0].wait_disconnected(timeout=5)
    dev[0].wait_connected(timeout=2, error="Timeout on reconnection")

def test_ap_open_assoc_timeout(dev, apdev):
    """AP timing out association"""
    ssid = "test"
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    dev[0].scan(freq="2412")
    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412",
                   wait_connect=False)
    for i in range(0, 10):
        req = hapd.mgmt_rx()
        if req is None:
            raise Exception("MGMT RX wait timed out")
        if req['subtype'] == 11:
            break
        req = None
    if not req:
        raise Exception("Authentication frame not received")

    resp = {}
    resp['fc'] = req['fc']
    resp['da'] = req['sa']
    resp['sa'] = req['da']
    resp['bssid'] = req['bssid']
    resp['payload'] = struct.pack('<HHH', 0, 2, 0)
    hapd.mgmt_tx(resp)

    assoc = 0
    for i in range(0, 10):
        req = hapd.mgmt_rx()
        if req is None:
            raise Exception("MGMT RX wait timed out")
        if req['subtype'] == 0:
            assoc += 1
            if assoc == 3:
                break
    if assoc != 3:
        raise Exception("Association Request frames not received: assoc=%d" % assoc)
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].wait_connected(timeout=15)

def test_ap_open_id_str(dev, apdev):
    """AP with open mode and id_str"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412", id_str="foo",
                   wait_connect=False)
    ev = dev[0].wait_connected(timeout=10)
    if "id_str=foo" not in ev:
        raise Exception("CTRL-EVENT-CONNECT did not have matching id_str: " + ev)
    if dev[0].get_status_field("id_str") != "foo":
        raise Exception("id_str mismatch")

def test_ap_open_select_any(dev, apdev):
    """AP with open mode and select any network"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    id = dev[0].connect("unknown", key_mgmt="NONE", scan_freq="2412",
                        only_add_network=True)
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412",
                   only_add_network=True)
    dev[0].select_network(id)
    ev = dev[0].wait_event(["CTRL-EVENT-CONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected connection")

    dev[0].select_network("any")
    dev[0].wait_connected(timeout=10)

def test_ap_open_unexpected_assoc_event(dev, apdev):
    """AP with open mode and unexpected association event"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected(timeout=15)
    dev[0].dump_monitor()
    # This will be accepted due to matching network
    subprocess.call(['iw', 'dev', dev[0].ifname, 'connect', 'open', "2412",
                     apdev[0]['bssid']])
    dev[0].wait_connected(timeout=15)
    dev[0].dump_monitor()

    dev[0].request("REMOVE_NETWORK all")
    dev[0].wait_disconnected(timeout=5)
    dev[0].dump_monitor()
    # This will result in disconnection due to no matching network
    subprocess.call(['iw', 'dev', dev[0].ifname, 'connect', 'open', "2412",
                     apdev[0]['bssid']])
    dev[0].wait_disconnected(timeout=15)

def test_ap_bss_load(dev, apdev):
    """AP with open mode (no security) configuration"""
    hapd = hostapd.add_ap(apdev[0]['ifname'],
                          { "ssid": "open",
                            "bss_load_update_period": "10" })
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412")
    # this does not really get much useful output with mac80211_hwsim currently,
    # but run through the channel survey update couple of times
    for i in range(0, 10):
        hwsim_utils.test_connectivity(dev[0], hapd)
        hwsim_utils.test_connectivity(dev[0], hapd)
        hwsim_utils.test_connectivity(dev[0], hapd)
        time.sleep(0.15)

def hapd_out_of_mem(hapd, apdev, count, func):
    with alloc_fail(hapd, count, func):
        started = False
        try:
            hostapd.add_ap(apdev['ifname'], { "ssid": "open" })
            started = True
        except:
            pass
        if started:
            raise Exception("hostapd interface started even with memory allocation failure: " + arg)

def test_ap_open_out_of_memory(dev, apdev):
    """hostapd failing to setup interface due to allocation failure"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    hapd_out_of_mem(hapd, apdev[1], 1, "hostapd_alloc_bss_data")

    for i in range(1, 3):
        hapd_out_of_mem(hapd, apdev[1], i, "hostapd_iface_alloc")

    for i in range(1, 5):
        hapd_out_of_mem(hapd, apdev[1], i, "hostapd_config_defaults;hostapd_config_alloc")

    hapd_out_of_mem(hapd, apdev[1], 1, "hostapd_config_alloc")

    hapd_out_of_mem(hapd, apdev[1], 1, "hostapd_driver_init")

    for i in range(1, 4):
        hapd_out_of_mem(hapd, apdev[1], i, "=wpa_driver_nl80211_drv_init")

    # eloop_register_read_sock() call from i802_init()
    hapd_out_of_mem(hapd, apdev[1], 1, "eloop_sock_table_add_sock;eloop_register_sock;?eloop_register_read_sock;=i802_init")

    # verify that a new interface can still be added when memory allocation does
    # not fail
    hostapd.add_ap(apdev[1]['ifname'], { "ssid": "open" })

def test_bssid_black_white_list(dev, apdev):
    """BSSID black/white list"""
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })
    hapd2 = hostapd.add_ap(apdev[1]['ifname'], { "ssid": "open" })

    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bssid_whitelist=apdev[1]['bssid'])
    dev[1].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bssid_blacklist=apdev[1]['bssid'])
    dev[2].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bssid_whitelist="00:00:00:00:00:00/00:00:00:00:00:00",
                   bssid_blacklist=apdev[1]['bssid'])
    if dev[0].get_status_field('bssid') != apdev[1]['bssid']:
        raise Exception("dev[0] connected to unexpected AP")
    if dev[1].get_status_field('bssid') != apdev[0]['bssid']:
        raise Exception("dev[1] connected to unexpected AP")
    if dev[2].get_status_field('bssid') != apdev[0]['bssid']:
        raise Exception("dev[2] connected to unexpected AP")
    dev[0].request("REMOVE_NETWORK all")
    dev[1].request("REMOVE_NETWORK all")
    dev[2].request("REMOVE_NETWORK all")

    dev[2].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bssid_whitelist="00:00:00:00:00:00", wait_connect=False)
    dev[0].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bssid_whitelist="11:22:33:44:55:66/ff:00:00:00:00:00 " + apdev[1]['bssid'] + " aa:bb:cc:dd:ee:ff")
    dev[1].connect("open", key_mgmt="NONE", scan_freq="2412",
                   bssid_blacklist="11:22:33:44:55:66/ff:00:00:00:00:00 " + apdev[1]['bssid'] + " aa:bb:cc:dd:ee:ff")
    if dev[0].get_status_field('bssid') != apdev[1]['bssid']:
        raise Exception("dev[0] connected to unexpected AP")
    if dev[1].get_status_field('bssid') != apdev[0]['bssid']:
        raise Exception("dev[1] connected to unexpected AP")
    dev[0].request("REMOVE_NETWORK all")
    dev[1].request("REMOVE_NETWORK all")
    ev = dev[2].wait_event(["CTRL-EVENT-CONNECTED"], timeout=0.1)
    if ev is not None:
        raise Exception("Unexpected dev[2] connectin")
    dev[2].request("REMOVE_NETWORK all")

def test_ap_open_wpas_in_bridge(dev, apdev):
    """Open mode AP and wpas interface in a bridge"""
    br_ifname='sta-br0'
    ifname='wlan5'
    try:
        _test_ap_open_wpas_in_bridge(dev, apdev)
    finally:
        subprocess.call(['ip', 'link', 'set', 'dev', br_ifname, 'down'])
        subprocess.call(['brctl', 'delif', br_ifname, ifname])
        subprocess.call(['brctl', 'delbr', br_ifname])
        subprocess.call(['iw', ifname, 'set', '4addr', 'on'])

def _test_ap_open_wpas_in_bridge(dev, apdev):
    hapd = hostapd.add_ap(apdev[0]['ifname'], { "ssid": "open" })

    br_ifname='sta-br0'
    ifname='wlan5'
    wpas = WpaSupplicant(global_iface='/tmp/wpas-wlan5')
    # First, try a failure case of adding an interface
    try:
        wpas.interface_add(ifname, br_ifname=br_ifname)
        raise Exception("Interface addition succeeded unexpectedly")
    except Exception, e:
        if "Failed to add" in str(e):
            logger.info("Ignore expected interface_add failure due to missing bridge interface: " + str(e))
        else:
            raise

    # Next, add the bridge interface and add the interface again
    subprocess.call(['brctl', 'addbr', br_ifname])
    subprocess.call(['brctl', 'setfd', br_ifname, '0'])
    subprocess.call(['ip', 'link', 'set', 'dev', br_ifname, 'up'])
    subprocess.call(['iw', ifname, 'set', '4addr', 'on'])
    subprocess.check_call(['brctl', 'addif', br_ifname, ifname])
    wpas.interface_add(ifname, br_ifname=br_ifname)

    wpas.connect("open", key_mgmt="NONE", scan_freq="2412")
