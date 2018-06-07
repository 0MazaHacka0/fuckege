import requests
import json
import os
import base64
import hashlib

base_path = "http://check.ege.edu.ru/"
# Api
captcha_uri = "api/captcha"
login_uri = "api/participant/login"

token = ""
captcha = ""

last_name_dict = ""


def solve_captcha():

    global captcha, token

    solved = False

    while not solved:
        print("Send GET to " + base_path + captcha_uri)

        r = requests.get(base_path + captcha_uri)
        _json = json.loads(r.text)
        image = _json['Image']
        token = _json['Token']

        print("Got new captcha")

        with open("image.jpg", "wb") as file:
            file.write(base64.decodebytes(image.encode()))

        print("Open captcha to solve")
        print("Enter code: ")
        os.system("start " + "image.jpg")
        captcha = int(input())

        status = requests.post(base_path + login_uri, data={
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
    r = requests.post(base_path + login_uri, data={
            "Captcha": captcha,
            "Code": code,
            "Document": document,
            "Hash": hash,
            "Region": region,
            "Token": token
        }).text
    return r


solve_captcha()
while True:
    solved = True

    # Pickup FullName
    code = ""
    document = ""
    hash = ""
    region = ""

    # Post it to site
    while not solved:

        solved = True

        result = send_request(code, document, hash, region)
        result_code = result.result_code

        # Check result
        if result_code == 204:
            print("Great job! Login success")
            print("Saving it to file")
            #save_good()
        elif result.text == '"Участник не найден"':
            print("Login failed. Trying next one")
        elif result.text == '"Пожалуйста, проверьте правильность введённого кода с картинки"':
            # Captcha die
            solved = False
            print("Captcha die, trying to get new one")
            solve_captcha()

    break
