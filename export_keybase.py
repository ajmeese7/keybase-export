#!/usr/bin/python3

import json
import sys
import os
import platform
from datetime import datetime

if len(sys.argv) < 2:
	print("Usage: " + sys.argv[0] + " <conversation name>")
	exit(1)

conv_name = sys.argv[1]
output_dir = conv_name.split(",")[1] if "," in conv_name else conv_name

# Specify a different root folder here if desired
conv_dir_root = os.path.normpath("./exports")
conv_dir = os.path.join(conv_dir_root, output_dir)
os.makedirs(conv_dir, exist_ok=True)

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

# Team chats have a different API format
if not "," in conv_name:
	initial_query = json.loads(initial_query)
	initial_query["params"]["options"]["channel"]["name"] = conv_name
	initial_query["params"]["options"]["channel"]["members_type"] = "team"
	initial_query = json.dumps(initial_query)

utc_timestamp = str(datetime.utcnow().timestamp())
date = datetime.now().strftime("%d-%m-%Y")
json_out = os.path.join(conv_dir, date + "_" + utc_timestamp + "_out.json")
log_out = os.path.join(conv_dir, date + "_" + utc_timestamp + "_conv.log")
attachment_queries = []
msg_stack = list()

def run_query(q):
	cmd = "echo '{}' | keybase chat api > {}".format(q, json_out)
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
	return os.path.join(conv_dir, "msg_id_" + get_msg_id(entry) + "_" + get_filename(entry))

def outputmsgs():
	with open(json_out, "r") as f:
		outputmsgs.json_data = json.load(f)

	if "error" in outputmsgs.json_data:
		print("Error: " + outputmsgs.json_data["error"]["message"])
		exit(1)

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
			attachment_query = json.dumps({
				"method": "download",
				"params": {
					"options": {
						"channel": {
							"name": conv_name
						},
						"message_id": int(mid),
						"output": file_name
					}
				}
			})
			attachment_queries.append((file_name, attachment_query))
		elif ctype == "attachmentuploaded":
			out = get_sender(entry) + " attachment " + mk_out_filename(entry) + " uploaded"
		elif ctype == "edit":
			edit = content["edit"]
			out = get_sender(entry) + " edited message with id " + str(edit["messageID"]) + " to: " + edit["body"]
		elif ctype == "delete":
			out = get_sender(entry) + " deleted message with ids " + str(content["delete"]["messageIDs"])
		elif ctype == "unfurl":
			out = get_sender(entry) + " sent unfurl: " + str(content["unfurl"]["unfurl"]["url"])
		elif ctype == "metadata":
			out = get_sender(entry) + " sent metadata: " + str(content["metadata"])
		elif ctype == "system":
			out = get_sender(entry) + " sent system message: " + str(content["system"])
		elif ctype == "none":
			pass
		else:
			out = "(unknown message type '" + ctype + "')"

		if out != "":
			msg_stack.append("#" + mid + " - " + datetime.utcfromtimestamp(sent_at).strftime("%Y-%m-%d %H:%M:%S") + " - " + out + "\n")
	res = not "last" in outputmsgs.json_data["result"]["pagination"]
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

with open(log_out, "a") as outfile:
	while msg_stack:
		msg = msg_stack.pop()
		outfile.write(msg)

print("downloading attachments...")

null_dir = "NUL" if platform.system() == "Windows" else "/dev/null"
for (file_name, attachment_query) in attachment_queries:
	print("downloading " + file_name)
	cmd = "echo {} | keybase chat api > {}".format(attachment_query, null_dir)
	os.system(cmd)

print("done")
