import requests
import subprocess
import sys
import os
import urllib3
import json

# Отключаем SSL предупреждения
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class KeyAuthAPI:
    def __init__(self, name, ownerid, secret, version, hash_to_check=None):
        self.name = name
        self.ownerid = ownerid
        self.secret = secret
        self.version = version
        self.hash_to_check = hash_to_check
        self.sessionid = None
        self.initialized = False
        self.init()

    def init(self):
        try:
            init_url = f"https://keyauth.win/api/1.1/?type=init&ver={self.version}&hash={self.hash_to_check}&name={self.name}&ownerid={self.ownerid}"
            response = requests.post(init_url, verify=False)
            
            if response.text == "KeyAuth_Invalid":
                print(f"[KeyAuth] App '{self.name}' not found")
                return

            json_data = response.json()
            if json_data["success"]:
                self.sessionid = json_data["sessionid"]
                self.initialized = True
            else:
                print(f"[KeyAuth] Init failed: {json_data.get('message')}")
        except Exception as e:
            print(f"[KeyAuth] Connection Error: {e}")

    def license(self, key):
        if not self.initialized: return False
        try:
            try: 
                hwid = str(subprocess.check_output('wmic csproduct get uuid', creationflags=0x08000000).decode('utf-8')).split('\n')[1].strip()
            except: 
                hwid = "Unknown"
            
            check_url = f"https://keyauth.win/api/1.1/?type=license&key={key}&hwid={hwid}&sessionid={self.sessionid}&name={self.name}&ownerid={self.ownerid}"
            response = requests.post(check_url, verify=False)
            json_data = response.json()
            
            if json_data["success"]: 
                return True
            return False
        except: 
            return False

    def var(self, name):
        if not self.initialized: return None
        try:
            url = f"https://keyauth.win/api/1.1/?type=var&varid={name}&sessionid={self.sessionid}&name={self.name}&ownerid={self.ownerid}"
            response = requests.post(url, verify=False)
            json_data = response.json()
            if json_data["success"]: 
                return json_data["message"]
            return None
        except: 
            return None
