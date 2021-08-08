import requests
import json
import random
from multiprocessing import Pool

new_token_url = "/api/new"
submit_url = "/api/questions/submit"
chars = "abcdefghijklmnopqrstuvwxyz"

times = 100
concurrency = 20
text_length = 500
question_owner = "owner"
question_type = "type"


def fire(bullet):
    return requests.post(submit_url, json.dumps(bullet['req']), headers={"authorization": "Bearer {}".format(bullet['token'])}).status_code


if __name__ == "__main__":
    bullets = list()
    for i in range(0, times):
        r = requests.get(new_token_url)
        token = r.json()['token']
        req = {
            "owner": question_owner,
            "type": question_type,
            "text": "".join([chars[random.randint(0, 25)] for i in range(0, text_length)])
        }
        bullets.append({'req': req, 'token': token})
        print(bullets[-1])

    with Pool(concurrency) as p:
        print(p.map(fire, bullets))
