#!/usr/bin/python3

import json
import sys
import os
from datetime import datetime

conv_name = sys.argv[1]
other_user = conv_name.split(",")[1]
conv_dir_root = "./exports/" # Specify a different root folder here if desired
conv_dir = conv_dir_root + other_user
os.makedirs(conv_dir)

pg = 1000
initial_query = json.dumps({
	"method": "read",
	"params": {
		"options": {
			"channel": {
				"name": conv_name,
				"pagination": {
					"num": pg
				}
			}
		}
	}
})

utc_timestamp = str(datetime.utcnow().timestamp())
date = datetime.now().strftime("%d-%m-%Y")
json_out = conv_dir + "/" + date + "_" + utc_timestamp + "_out.json"
log_out = conv_dir + "/" + date + "_" + utc_timestamp + "_conv.log"
query_dl = []
msg_stack = list()

def run_query(q):
	cmd = "echo {} | keybase chat api > {}".format(q, json_out)
	os.system(cmd)

run_query(initial_query)

def get_content_type(entry):
	return entry["msg"]["content"]["type"]

def get_sender(entry):
	return entry["msg"]["sender"]["username"]

def get_msg_id(entry):
	return str(entry["msg"]["id"])

def get_filename(entry):
	ctype = get_content_type(entry)
	if ctype == "attachment":
		return entry["msg"]["content"]["attachment"]["object"]["filename"]
	elif ctype == "attachmentuploaded":
		return entry["msg"]["content"]["attachment_uploaded"]["object"]["filename"]
	else:
		print("don't know how to get filename")
		exit(1)

def mk_out_filename(entry):
		return conv_dir + "/msg_id_" + get_msg_id(entry) + "_" + get_filename(entry)

def outputmsgs():
	with open(json_out, 'r') as f:
		outputmsgs.json_data = json.load(f)

	output_messages = filter(
		# Filters out all the errored messages, most commonly messages that have since exploded
		lambda x: not x.__contains__("error"),
		outputmsgs.json_data["result"]["messages"]
	)

	for entry in output_messages:
		out = ""
		ctype = get_content_type(entry)
		mid = get_msg_id(entry)
		content = entry["msg"]["content"]
		sent_at = entry["msg"]["sent_at"]
		if ctype == "text":
			out = "<" + get_sender(entry) + "> " + content["text"]["body"]
		elif ctype == "reaction":
			out = "* " + get_sender(entry) + ": " + content["reaction"]["b"]
		elif ctype == "attachment":
			file_name = mk_out_filename(entry)
			out = get_sender(entry) + " sent attachment " + file_name
			attachment_query = '{"method": "download", "params": {"options": {"channel": {"name": "' + conv_name + '"}, "message_id": ' + mid + ', "output": "' + file_name + '"}}}'
			query_dl.append((file_name, attachment_query))
		elif ctype == "attachmentuploaded":
			out = get_sender(entry) + " attachment " + mk_out_filename(entry) + " uploaded"
		elif ctype == "edit":
			edit = content["edit"]
			out = get_sender(entry) + " edited message with id " + str(edit["messageID"]) + " to: " + edit["body"]
		elif ctype == "delete":
			out = get_sender(entry) + " deleted message with ids " + str(content["delete"]["messageIDs"])
		elif ctype == "unfurl":
			out = get_sender(entry) + " sent unfurl: " + str(content["unfurl"]["unfurl"]["url"])
		else:
			out = "(unknown message type '" + ctype + "')"
		msg_stack.append("#" + mid + " - " + datetime.utcfromtimestamp(sent_at).strftime('%Y-%m-%d %H:%M:%S') + " - " + out + '\n')
	res = not 'last' in outputmsgs.json_data["result"]["pagination"]
	if res:
		outputmsgs.next = outputmsgs.json_data["result"]["pagination"]["next"]
	return res

print("exporting messages...")

while outputmsgs():
	output_query = json.dumps({
		"method": "read",
		"params": {
			"options": {
				"channel": {
					"name": conv_name,
					"pagination": {
						"next": outputmsgs.next,
						"num": pg
					}
				}
			}
		}
	})
	run_query(output_query)

with open(log_out, 'a') as outfile:
	while msg_stack:
		msg = msg_stack.pop()
		outfile.write(msg)

print("downloading attachments...")

for (f, q) in query_dl:
	# TODO: Unbreak this error - "The system cannot find the path specified."
	print("downloading " + f)
	cmd = "echo {} | keybase chat api > /dev/null".format(q)
	os.system(cmd)
