
from random import random
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import json
import time
import telegram
from telegram.ext import Updater
from telegram.ext import CommandHandler

'''

GPSs => [
    (Telegram_id) => [
        GPS => [위도, 경도],
        last_time => 0000,
        status => (boolean) # true : 외출 상황, false : 외출 상황 아님,
        disconnected => (boolean) # true : 긴급 상황, false : 긴급 상황 아님
    ]
]

FRIENDS => [
    (Telegram id) => [(Friend 1 Telegram id), (Friend 2 Telegram id)]
]

REGISTER => [
    (Telegram id) => [
        status => (boolean) # True : 인증 완료, False : 인증 완료 안 됨
        code => (integer) # 6자리 숫자 원래 코드
        sent_code => (integer) #  휴대폰에서 보낸 6자리 코드
    ]
]

'''


# 파이어베이스 설정

cred = credentials.Certificate("path/to/serviceAccountKey.json") # TODO 파일명 변경 필요
firebase_admin.initialize_app(cred, {
    'databaseURL' : 'https://skku-pikachu-default-rtdb.firebaseio.com/'
})


# 텔레그램 설정

token = "" # TODO 토큰 알아오기
bot = telegram.Bot(token)


'''

텔레그램 CommandHandler 설정

명령어 종류 : register, delete, friends

'''

updater = Updater(token=token, use_context=True)


def register_friend(update, context): # 사용자가 친구를 등록

    friend_id = context.args[0]

    context.bot.send_message(chat_id=update.effective_chat.id, text= friend_id + "를 응급 연락처에 저장합니다. 사용자님은 이 사실을 /delete를 통해 취소할 수 있습니다.")

    friends = db.reference('FREINDS/' + update.effective_chat.id).get()
    friends.append(friend_id)
    db.reference('FREINDS/' + update.effective_chat.id).update(friends)

updater.dispatcher.add_handler(CommandHandler('register', register_friend))


def delete_friend(update, context): # 사용자가 친구를 자신의 긴급연락처에 존재하는 것을 거절

    friend_id = context.args[0]

    friends_in_me = db.reference('FREINDS/' + update.effective_chat.id).get()

    if friend_id not in friends_in_me:

        context.bot.send_message(chat_id=update.effective_chat.id, text= friend_id + "님은 사용자와 친구가 아닙니다.")

    else:

        context.bot.send_message(chat_id=update.effective_chat.id, text= friend_id + "님과 친구를 취소합니다.")

        friends_in_me.remove(friend_id) # 나의 연락처에 친구 삭제

        db.reference('FREINDS/' + update.effective_chat.id).update(friends)


updater.dispatcher.add_handler(CommandHandler('delete', delete_friend))


def friend_list(update, context): # 자신의 친구 조회

    friends = db.reference('FREINDS/' + update.effective_chat.id).get()

    context.bot.send_message(chat_id=update.effective_chat.id, text= "응급 연락처에 존재하는 친구 목록을 보내드립니다.")

    for friend_id in friends:

        context.bot.send_message(chat_id=update.effective_chat.id, text= friend_id)
    
    context.bot.send_message(chat_id=update.effective_chat.id, text= "끝")


updater.dispatcher.add_handler(CommandHandler('friends', friend_list))


updater.start_polling()


'''

LOOP

'''

while True:

    '''

        핸드폰 상태 파악
    
    '''

    datas = db.reference('GPSs').get()

    datas = json.loads(datas)

    for tele_id in datas.keys():

        if not datas[tele_id]["status"]: # 외출 상황인지 확인
            continue

        if datas[tele_id]["last_time"] >= time.time() + 60 * 10: # 10분 이상 지났을 시

            db.reference('GPSs/' + tele_id + '/disconnected').update(True) # 데이터 베이스에 위험 표시 ON

            friends = db.reference('FREINDS/' + tele_id)
            
            for friend in friends:
                
                bot.sendMessage(chat_id=friend, text="현재 " + tele_id + "님이 10분동안 연결이 안 됩니다! 도와주세요.")
                bot.sendMessage(chat_id=friend, text="GPS 위도 : " + datas[tele_id]["GPS"][0] + ", GPS 경도 : " + datas[tele_id]["GPS"][1])
        
        elif datas[tele_id]["disconnected"]: # 10분 이상 안 지났는데 disconnected 가 계속 이루어지면

            db.reference('GPSs/' + tele_id + '/disconnected').update(False) # 데이터 베이스에 위험 표시 ON
            
            friends = db.reference('FREINDS/' + tele_id).get()

            for friend in friends:

                bot.sendMessage(chat_id=friend, text="" + tele_id + "님의 연결이 회복되었습니다. 감사합니다.")
    
    '''

        텔레그램 인증 절차

        핸드폰에서 데이터베이스 생성 -> 서버에서 code 업데이트 -> 핸드폰에서 sent_code 업데이트 -> 서버에서 대조 후 맞으면 status 업데이트 -> 핸드폰에서 GPSs랑 Friends 등록

    '''

    register_datas = db.reference('REGISTER').get()

    register_datas = json.loads(register_datas)

    for tele_id in register_datas:

        if not register_datas[tele_id]['status'] and register_datas[tele_id]['code'] == 0: # 핸드폰에서 시도를 하면 인증번호를 만들고 보내기

            code = random.randrange(1, 999999)
            register_datas[tele_id]['code'] == code
            bot.sendMessage(chat_id = tele_id, text = "인증번호 [" + code + "]")
        
        if not register_datas[tele_id]['status'] and register_datas[tele_id]['code'] is not 0: # 핸드폰에서 인증번호를 보냈으면 비교하고 맞으면 status 업데이트하기

            if register_datas[tele_id]['code'] == register_datas[tele_id]['sent_code']:

                db.reference('REGISTER/' + tele_id + "/status").update(True)
            
            else:

                db.reference('REGISTER/' + tele_id + "/sent_code").update(-1)
                

    if not db.reference("server_status").get():
        break