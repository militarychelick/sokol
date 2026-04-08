# -*- coding: utf-8 -*-
"""
SOKOL v8.0 — Information Hub
Facts, jokes, and interesting data.
"""

INFO_DATA = {
    "jokes": [
        "Почему программисты не любят природу? Слишком много багов.",
        "Заходит бесконечное число математиков в бар. Первый заказывает кружку пива, второй — полкружки, третий — четверть... Бармен говорит: 'Парни, я знаю меру', и наливает две кружки.",
        "Программист ложится спать и ставит на тумбочку два стакана. Один с водой — если захочет пить, другой пустой — если не захочет.",
        "Hardware — это то, что можно ударить ногой. Software — то, что можно только обматерить.",
    ],
    "facts": [
        "Мёд никогда не портится. Археологи находили съедобный мёд в гробницах возрастом 3000 лет.",
        "У осьминогов три сердца и голубая кровь.",
        "Самая высокая гора в Солнечной системе — Олимп на Марсе, её высота 21 км.",
        "Первый компьютерный вирус 'Creeper' был создан в 1971 году.",
        "Шахматы были изобретены в Индии примерно в VI веке.",
    ],
    "popular_sites": {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "vk": "https://vk.com",
        "yandex": "https://yandex.ru",
        "github": "https://github.com",
        "telegram": "https://web.telegram.org",
        "whatsapp": "https://web.whatsapp.com",
        "reddit": "https://www.reddit.com",
        "wikipedia": "https://www.wikipedia.org",
        "netflix": "https://www.netflix.com",
        "amazon": "https://www.amazon.com",
        "twitter": "https://twitter.com",
        "instagram": "https://www.instagram.com",
        "facebook": "https://www.facebook.com",
        "habr": "https://habr.com",
        "mail": "https://mail.ru",
        "ozon": "https://ozon.ru",
        "wildberries": "https://wildberries.ru",
        "avito": "https://avito.ru",
        "discord": "https://discord.com",
    },
    "history": [
        "18 век: Петр I основал Санкт-Петербург в 1703 году и провозгласил Россию империей в 1721.",
        "18 век: Елизавета Петровна основала Московский университет в 1755 году.",
        "18 век: При Екатерине II Крым вошел в состав России в 1783 году.",
        "ВМВ: Тегеранская конференция 1943 года стала первой встречей Сталина, Рузвельта и Черчилля.",
        "ВМВ: Ялтинская конференция 1945 года определила послевоенное устройство мира.",
        "ВМВ: Акт о капитуляции Германии был подписан 8 мая 1945 года в Берлине (Карлсхорст).",
    ],
}

import random

class InfoHub:
    @classmethod
    def get_history_fact(cls):
        return random.choice(INFO_DATA["history"])
    @classmethod
    def get_joke(cls):
        return random.choice(INFO_DATA["jokes"])

    @classmethod
    def get_fact(cls):
        return random.choice(INFO_DATA["facts"])

    @classmethod
    def get_popular_site(cls, name):
        n = name.lower().strip()
        return INFO_DATA["popular_sites"].get(n)
