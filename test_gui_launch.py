#!/usr/bin/env python3
"""Test GUI components without displaying windows."""

import sys
import os

# Set up paths
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_gui_imports():
    """Test that GUI components can be imported."""
    try:
        from gui.main_window import MainWindow, ActivityListWidget, ActivityDetailsWidget
        from config.settings import Config
        from models.activity import Activity
        print("✅ All GUI imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_gui_creation():
    """Test creating GUI components without displaying them."""
    try:
        # Set up headless mode for testing
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'

        from PyQt6.QtWidgets import QApplication
        from gui.main_window import ActivityListWidget, ActivityDetailsWidget
        from config.settings import Config
        from models.activity import Activity
        from datetime import datetime

        # Create QApplication (required for Qt widgets)
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # Test creating widgets
        list_widget = ActivityListWidget()
        details_widget = ActivityDetailsWidget()

        # Test with sample activity
        activity = Activity(
            id=1, name='Test Run', type='Run', distance=5000.0,
            moving_time=1200, elapsed_time=1250, total_elevation_gain=50.0,
            start_date=datetime.now(), start_date_local=datetime.now(),
            timezone='UTC', achievement_count=0, kudos_count=0,
            comment_count=0, athlete_count=1, photo_count=0,
            trainer=False, commute=False, manual=False, private=False,
            flagged=False, gear_id=None, average_speed=4.17, max_speed=5.5,
            has_heartrate=False, average_heartrate=None, max_heartrate=None,
            heartrate_opt_out=False, display_hide_heartrate_option=False,
            elev_high=None, elev_low=None, pr_count=0, total_photo_count=0,
            has_kudoed=False
        )

        # Test setting activities
        list_widget.set_activities([activity])
        details_widget.set_activity(activity)

        print("✅ GUI components created successfully!")
        print(f"✅ Activity list has {list_widget.count()} items")
        print("✅ Activity details widget populated")

        return True

    except Exception as e:
        print(f"❌ GUI creation error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing GUI components...")
    print("=" * 40)

    if test_gui_imports() and test_gui_creation():
        print("\n🎉 All GUI tests passed! The application should work correctly.")
        print("To run the full GUI, use: PYTHONPATH=src python main.py")
    else:
        print("\n❌ Some GUI tests failed.")