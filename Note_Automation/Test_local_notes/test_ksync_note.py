import allure
import logging
from selenium.webdriver.common.by import By
from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Test_local_notes.Public_method import Public_method
from Note_Automation.config import driver
from Note_Automation.conftest import note_mark_china, get_device_info, note_mark_increment



class Test_ksync_note:

    def setup_method(self):

        self.driver = driver

        self.method = Operation_method(self.driver)

        self.public = Public_method()


    def test_10_ksync_onyx(self):

        pass

    def test_11_ksync_baidu(self):

        pass




