#!/usr/bin/env python3

import os
from otvetmailru import OtvetClient


AUTH_FILE = 'auth_info.txt'


if os.path.isfile(AUTH_FILE):
    with open(AUTH_FILE) as f:
        client = OtvetClient(auth_info=f.read())
else:
    client = OtvetClient()
if not client.check_authentication():
    email = input('email> ')
    password = input('password> ')
    client.authenticate(email, password)
with open('auth_info.txt', 'w') as f:
    f.write(client.auth_info)

me = client.get_user()
print(f'Authenticated as {client.user_id} ({me.name}, {me.rate.name})')
print(me.url)
print()


for questions in client.iterate_new_questions():
    for question in questions:
        question = client.get_question(question)
        if not question.can_answer:
            continue

        print(f'{question.author.name} in {question.category.name}')
        print(question.url)
        print(question.title)
        print(question.text)

        if not question.poll_type:
            answer = input('answer> ').strip()
            print()
            if not answer:
                continue
            client.add_answer(question, answer)
        else:
            print(f'Poll ({question.poll_type.value})')
            for i, option in enumerate(question.poll.options, 1):
                print(f'{i}) {option.text}')
            print()
            vote = list(map(int, input('vote> ').split()))
            selected = [question.poll.options[i - 1] for i in vote]
            client.vote_in_poll(question, selected)
            print()
