import logging
import re
from collections import Counter
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, PEP_URL
from outputs import control_output
from utils import find_tag, get_response


def whats_new(session):
    """
    Получает информацию о последних изменениях в
    документации Python на странице "whatsnew/".

    Аргументы:
        session:  Объект CachedSession из библиотеки requests_cache,
                  который используется для кэширования запросов.

    Возвращает:
        list: Список кортежей с информацией о
              последних изменениях в документации Python.
              Каждый кортеж содержит:
              - Ссылку на статью (str).
              - Заголовок (str).
              - Редактор и автор (str).
    """
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'})

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        version_link = urljoin(whats_new_url, version_a_tag['href'])
        response = get_response(session, version_link)
        if response is None:
            continue

        soup = BeautifulSoup(response.text, 'lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')

        results.append((version_link, h1.text, dl_text))

    return results


def latest_versions(session):
    """
    Получает информацию о последних доступных версиях Python и
    их статусах из главной страницы документации.

    Аргументы:
        session: Объект CachedSession из библиотеки requests_cache,
                 который используется для кэширования запросов.

    Возвращает:
        list: Список кортежей с информацией о последних
              доступных версиях Python и их статусах.
              Каждый кортеж содержит:
              - Ссылку на документацию (str).
              - Версию Python (str).
              - Статус версии (str).

    Исключения:
        Exception: Возникает, если не найдено
                   содержание с ссылками на версии Python.
    """
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, 'lxml')

    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')

    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version = text_match.group('version')
            status = text_match.group('status')
        else:
            version = a_tag.text
            status = ''
        results.append([link, version, status])
    return results


def download(session):
    """
    Скачивает архив "pdf-a4.zip" с документацией Python
    из страницы "download.html".

    Аргументы:
        session: Объект CachedSession из библиотеки requests_cache,
                 который используется для кэширования запросов.
    """
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')

    response = get_response(session, downloads_url)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, 'lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')})
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]

    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    """
    Данная функция выполняет парсинг страницы PEP и считает
    количество PEP с разными статусами.

    Args:
        session: Объект CachedSession из библиотеки requests_cache,
                 который используется для кэширования запросов.

    Returns:
        list: Список кортежей с результатами статистики. Каждый кортеж содержит
            статус PEP и соответствующее количество.
    """
    pep_status_counter = Counter()
    results = [('Статус', 'Количество')]

    response = get_response(session, PEP_URL)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, 'lxml')

    # Находим основной раздел, содержащий все PEP
    big_section = find_tag(soup, 'section', attrs={'id': 'index-by-category'})

    sections = big_section.find_all('section')

    for section in tqdm(sections):
        # Находим таблицу, содержащую информацию о PEP
        table = section.table

        # Используем множество для хранения уникальных значений href
        # чтобы избежать обработки дубликатов
        cached_href = set()

        if not table:
            continue

        for td in tqdm(table.find_all('td')):
            if td.abbr:
                section_status = td.abbr.text[1:]
                section_status = EXPECTED_STATUS[section_status]
            if td.a and td.a['href'] not in cached_href:
                href = td.a['href']
                cached_href.add(href)
                full_href = urljoin(PEP_URL, href)
                response = get_response(session, full_href)
                soup = BeautifulSoup(response.text, 'lxml')
                table_text = find_tag(soup, 'dl').text
                page_status = table_text.split('Status:')[-1].split()[0]
                if page_status in section_status:
                    pep_status_counter[section_status] += 1
                else:
                    logging.info(
                        f'Статус в карточке "{full_href}" отображен как '
                        f'"{page_status}", что не соотносится '
                        f'с {section_status}')
        cached_href.clear()
        print(pep_status_counter.items())
    results.extend((', '.join(k), v) for k, v in pep_status_counter.items())
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    """
    Главная функция для запуска парсера документации Python.
    """
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
