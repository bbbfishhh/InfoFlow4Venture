import http.client
import hashlib
import urllib
import random
import json
import os

class BaiduTranslateAPI:
    def __init__(self, appid, secretKey):
        """
        初始化百度翻译API

        :param appid: 百度翻译API的appid
        :param secretKey: 百度翻译API的密钥
        """
        self.appid = appid
        self.secretKey = secretKey

    def translate(self, q, fromLang='auto', toLang='zh'):
        """
        进行翻译

        :param q: 需要翻译的文本
        :param fromLang: 原文语种，默认为自动检测
        :param toLang: 译文语种，默认为中文
        :return: 翻译结果
        """
        salt = random.randint(32768, 65536)
        sign = self.appid + q + str(salt) + self.secretKey
        sign = hashlib.md5(sign.encode()).hexdigest()
        myurl = '/api/trans/vip/translate?appid=' + self.appid + '&q=' + urllib.parse.quote(q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign

        try:
            httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
            httpClient.request('GET', myurl)

            # response是HTTPResponse对象
            response = httpClient.getresponse()
            result_all = response.read().decode("utf-8")
            result = json.loads(result_all)

            return result
        except Exception as e:
            print(e)
        finally:
            if httpClient:
                httpClient.close()


# 使用示例
appid = os.getenv('BAIDU_APPID')
secretKey = os.getenv('BAIDU_SECRET_KEY')
translate_api = BaiduTranslateAPI(appid, secretKey)
sentences = "Anthropic CEO Dario Amodei believes scaling up AI models remains viable for achieving more capable AI, despite evidence suggesting otherwise. He doesn't foresee data shortages hindering development, suggesting synthetic data or extrapolation as solutions. Amodei acknowledges rising AI compute costs, predicting billions in spending next year, escalating to hundreds of billions by 2027. He admits the unpredictability of even the best models and anticipates superintelligent AI by 2026 or 2027, expressing concerns about potential abuse of power.  Google has developed an improved AI flood forecasting model, predicting conditions up to seven days in advance globally.  A new Minecraft-simulating model, Lucid v1, can run on a single Nvidia RTX 4090, offering real-time game world emulation."
result = translate_api.translate(sentences)
print(result)