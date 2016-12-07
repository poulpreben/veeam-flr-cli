#!/usr/bin/python
import getpass
import re
import requests
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import xml.etree.ElementTree as ET
import xml.dom.minidom
import urllib2
from time import sleep

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

api_url = 'https://veaam.domain.local:9398/api/'
session = False

## Functions

# Because Python is a little stupid and prefixes everything with the damn namespace
def remove_namespace(data):
	result = re.sub(' xmlns="[^"]+"', '', data, count=1)
	return result

def create_session(username, password):
	global session

	session = requests.Session()
	r = session.post(api_url+'/sessionMngr/?v=latest', auth=(username, password), verify=False)

	links      = ET.fromstring(remove_namespace(r.content))
	session_id = links.find("SessionId").text

	return session_id

def delete_session(session_id):
	r = session.delete(api_url+'/logonSessions/'+session_id)

	return

def list_catalog(name):
	r = session.get(api_url+'/catalog/vms?format=Entity')
	vms = ET.fromstring(remove_namespace(r.content))

	result = []

	for rp in list(vms[0][0]):
		if (rp.attrib.get("Name")):
			vm_name      = rp.attrib.get("Name")
			catalog_link = rp.attrib.get("Href")

			if (vm_name == name):
				vm_info = dict(vm_name=vm_name, catalog_link=catalog_link)
				result.append(vm_info)

	return result

def catalog_restore_points(name):
	catalog_name = urllib2.quote(name)
	r = session.get(api_url+'/catalog/vms/'+catalog_name+'/vmRestorePoints?format=Entity&sort=BackupDateUTC')
	rps = ET.fromstring(remove_namespace(r.content))

	result = []
	if len(rps) == 0:
		return result

	for rp in list(rps[0][0]):
		if (rp.attrib.get("Rel") == "Alternate"):
			vm_name      = rp.attrib.get("Name")
			url          = rp.attrib.get("Href")

			vm_info = dict(vm_name=vm_name, url=url)
			result.append(vm_info)

	return result

def prepare_browse(url):
	url = url + '?action=browse'
	r = session.post(url, verify=False)
	if (r.status_code == 200):
		return True
	else:
		return False

def check_file(url, f):
	url = url + '/guestfs/' + urllib2.quote(f)
	r = session.get(url)
	print debug(r.content)

	if r.status_code == 200:
		return True
	else:
		return False

def restore_file(url, f):
	url = url + '/guestfs/' + urllib2.quote(f) + '?action=restore'
	r = session.post(url, verify=False)

	restore_status = ET.fromstring(remove_namespace(r.content))

	task_id    = restore_status.find("TaskId").text
	task_state = restore_status.find("State").text

	print "File-level restore assigned with " + task_id

	while task_state == "Running":
		print "Waiting for FLR to start."
		sleep(10)
		r = session.get(api_url+"/tasks/"+task_id)
		restore_status = ET.fromstring(remove_namespace(r.content))
		task_state = restore_status.find("State").text

	if restore_status.find("Result").attrib.get("Success") == "false":
		return False
	else:
		return "FLR is now running."

def get_restore_session(task_id):
	r = session.get(api_url+'/tasks/'+task_id)
	rc = ET.fromstring(remove_namespace(r.content))

	for i in list(rc[0]):
		print i

def debug(xmlString):
	data   = xml.dom.minidom.parseString(xmlString)
	pretty = data.toprettyxml()

	return pretty


## Runtime code
print "Python Linux FLR Tool for Veeam 9.5 / EM 9.5"
print " "
em_user = raw_input("EM username: ")
em_pass = False
em_pass = getpass.getpass("EM password: ")

session_id = create_session(em_user, em_pass)

vm_name = raw_input("Enter VM name: ")
catalog = catalog_restore_points(vm_name)

if len(catalog) > 0:
	print "Found restore point. Preparing..."
	print " "
	url = catalog[-1]['url']
	if prepare_browse(url):
		f = raw_input("Enter file name to restore: ")
		print " "

		if restore_file(url, f):
			print "Restore of file '%s' initiated." % f
		else:
			print "Restore failed."
	else:
		print "Could not open guest catalog."
else:
	print "No index found for VM with name '%s'" % vm_name

delete_session(session_id)
