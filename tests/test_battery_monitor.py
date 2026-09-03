"""
Unit tests for HA Battery Monitor core functionality.
Executable via:
    python -m unittest discover tests
or:
    pytest tests/
"""
import sys
import unittest
import tempfile
import json
from pathlib import Path
from collections import namedtuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import battery_monitor as bm

BatteryTuple = namedtuple('BatteryTuple', ['percent', 'secsleft', 'power_plugged'])


class TestBatteryAlerts(unittest.TestCase):
    """Test battery alert evaluation logic across levels."""

    def setUp(self):
        bm.load_settings()

    def test_unplugged_critical_low(self):
        battery = BatteryTuple(percent=15, secsleft=1800, power_plugged=False)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertTrue(should_alert)
        self.assertEqual(level, 'critical_low')
        self.assertIn('CRITICAL', msg)

    def test_unplugged_warning_low(self):
        battery = BatteryTuple(percent=24, secsleft=3600, power_plugged=False)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertTrue(should_alert)
        self.assertEqual(level, 'warning_low')
        self.assertIn('WARNING', msg)

    def test_unplugged_notice_low(self):
        battery = BatteryTuple(percent=29, secsleft=4000, power_plugged=False)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertTrue(should_alert)
        self.assertEqual(level, 'notice_low')

    def test_unplugged_normal_charge(self):
        battery = BatteryTuple(percent=65, secsleft=7200, power_plugged=False)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertFalse(should_alert)
        self.assertIsNone(msg)
        self.assertIsNone(level)

    def test_plugged_high_critical(self):
        battery = BatteryTuple(percent=95, secsleft=-1, power_plugged=True)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertTrue(should_alert)
        self.assertEqual(level, 'high_critical')

    def test_plugged_high_warning(self):
        battery = BatteryTuple(percent=86, secsleft=-1, power_plugged=True)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertTrue(should_alert)
        self.assertEqual(level, 'high_warning')

    def test_plugged_high_notice(self):
        battery = BatteryTuple(percent=81, secsleft=-1, power_plugged=True)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertTrue(should_alert)
        self.assertEqual(level, 'high_notice')

    def test_plugged_normal_charge(self):
        battery = BatteryTuple(percent=50, secsleft=-1, power_plugged=True)
        should_alert, msg, level = bm.check_battery_alerts_v2(battery)
        self.assertFalse(should_alert)


class TestConfigManagement(unittest.TestCase):
    """Test configuration loading, saving, and path resolution."""

    def test_config_path_resolution(self):
        cfg_path = bm.get_config_path()
        self.assertIsInstance(cfg_path, Path)
        self.assertTrue(str(cfg_path).endswith('battery_config.json'))

    def test_load_and_save_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_cfg = Path(tmpdir) / 'battery_config.json'
            orig_cfg = bm.config_file
            bm.config_file = test_cfg
            try:
                bm.load_settings()
                self.assertIn('monitoring', bm.app_settings)
                self.assertIn('notifications', bm.app_settings)
                self.assertIn('audio', bm.app_settings)
                bm.app_settings['monitoring']['low_critical'] = 18
                bm.save_settings()
                self.assertTrue(test_cfg.exists())
                with open(test_cfg, 'r') as f:
                    saved_data = json.load(f)
                self.assertEqual(saved_data['monitoring']['low_critical'], 18)
            finally:
                bm.config_file = orig_cfg


class TestSingleInstance(unittest.TestCase):
    """Test single-instance lock and release."""

    def test_single_instance_lifecycle(self):
        bm.cleanup_single_instance()
        try:
            is_first = bm.create_single_instance_check()
            self.assertTrue(is_first, "First instance acquisition should succeed")
        finally:
            bm.cleanup_single_instance()


class TestSanitization(unittest.TestCase):
    """Test notification escaping and sanitization helpers."""

    def test_xml_escaping(self):
        import html
        dangerous_input = 'Alert: Battery < 10% & status == "critical" > shutdown'
        escaped = html.escape(dangerous_input)
        self.assertNotIn('<', escaped)
        self.assertNotIn('>', escaped)
        self.assertIn('&lt;', escaped)
        self.assertIn('&gt;', escaped)
        self.assertIn('&amp;', escaped)


if __name__ == '__main__':
    unittest.main()
