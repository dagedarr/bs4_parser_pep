import logging

from requests import RequestException

from exceptions import ParserFindTagException


# Перехват ошибки RequestException.
def get_response(session, url):
    """
    Выполняет GET-запрос по указанному URL и
    обрабатывает ошибки RequestException.

    Аргументы:
        session: Объект CachedSession из библиотеки requests_cache,
                 который используется для кэширования запросов.
        url (str): URL для выполнения GET-запроса.

    Возвращает:
        requests.models.Response: Объект Response, содержащий ответ на запрос.

    Примечание:
        В случае возникновения ошибки RequestException,
        будет записано сообщение в журнал с информацией о
        стеке вызовов и выполнение функции продолжится без прерывания.
    """
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}',
            stack_info=True
        )


# Перехват ошибки поиска тегов.
def find_tag(soup, tag, attrs=None):
    """
    Выполняет поиск тега в объекте BeautifulSoup и обрабатывает
    ошибку ParserFindTagException.

    Аргументы:
        soup (BeautifulSoup): Объект BeautifulSoup, представляющий
                              HTML-код страницы.
        tag (str): Имя тега, который необходимо найти.
        attrs (dict, optional): Атрибуты тега (словарь), по которым
                                выполняется поиск (по умолчанию None).

    Возвращает:
        Tag: Объект Tag из библиотеки BeautifulSoup, соответствующий
             найденному тегу.

    Исключения:
        ParserFindTagException: Возникает, если указанный тег не
                                найден в объекте BeautifulSoup.

    Примечание:
        В случае, если тег не найден, будет записано сообщение в журнал с
        информацией о стеке вызовов, и будет возбуждено
        исключение ParserFindTagException.
    """
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag
