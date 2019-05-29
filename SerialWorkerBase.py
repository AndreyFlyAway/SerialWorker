# -*- coding: utf-8 -*-
'''@file serialWorkerBase.py
@brief  базовый класс, обеспечивающий корректную запись команд и парсинг ответов, при распаковывании ядра на целевую платформу
@author Yanikeev-as
@version 2.1
@date 2018-10-18
'''

import configparser
import StringIO
import time, re, os
from serial import Serial
from serial.serialutil import SerialException
from PySide.QtCore import QThread
from PySide.QtCore import Signal
from Queue import Queue

""" constants """
CLEAN_BUFFER_TIMEOUT = 45
LOG_FILE_NAME = "logout_{0}.txt"
LOG_DIR_NAME = "logout"
ATTEMPTS_NUM = 3

""" коды удачного результата """
COMMAND_SUCCESS_CODE = 1
STEP_SUCCESS_CODE = 2
TOTAL_SUCCESS_CODE = 3
CONNECT_SUCCESS_CODE = 4

""" коды ошибок """
CLEAN_INBUF_TIMEOT_ERR = -1
ANSWER_MATCH_ERR = -2
CONNECTION_ERROR = -3

""" для шифрования """
IV_VAL = 16

class SerialWorkerBase(QThread):
    """
    базовый класс, обеспечивающий методы загрузки дистрибутива и общения с графической часью
    """
    sig_faoult = Signal(int) # сигнализирует об ошибке, передает код ошибки
    sig_progress_increase = Signal() # для равномерного увеличения прогремма загруки
    sig_load_step_done = Signal(int) # сигнализирует об удачном завершении этапа, через сигнал передается номер этапа
    sig_end_load = Signal() # сигнализирует об удачном завершении этапа, через сигнал передается номер этапа
    sig_error = Signal(object) # сигнализирует об возникновении ошбки
    ste_name_dict = {} # словарь, который должен содержать соспостовление номера шага и текстового значение
    passwd = "Htkbpysqgfhjkmlkz.pthf" # стандартный пароль

    def __init__(self, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.input_buffer = "" # по этой ссылке храниться все входящие данные от последовательного порта
        self.out_cmd_queue = Queue() # в очередь кладутся словари формата {"command": комманда, "expected_regexp": RegExp ожидаемого ответа,
        #  "additionTimeout": дополнительный таймут между ответами, по умоличани это 0}
        self.standart_timeout = 0.1
        # self._config_object = config_object
        self.last_answer = None # последний ответ, на случай если произошла ошибка в процессе запросов
        self.last_request = None # последний запрос, на случай если произошла ошибка в процессе запросов
        self.debug_msg = None # debug сообщение, в случае неудачного запроса
        self.steps = 0 # шаги, которые нужно выполнить
        self.total_cmd_commands = 0 # полное количество последовательных команд

    def connect_to_port(self, port, baudrate):
        """
        подлкючение к последовательному порту
        :param port: название порта для подключения
        :param baudrate: скорость для подключения
        :return:
        """
        self.port = port
        self.baudrate = baudrate
        try:
            self.connection_obj = Serial(self.port, self.baudrate, timeout=0.1)
            return CONNECT_SUCCESS_CODE
        except SerialException:
            self.debug_msg = u"Потеряно соединения!"
            return CONNECTION_ERROR

    def disconnect_port(self):
        """
        отключение от порта
        :return:
        """
        self.connection_obj.close()

    def poll_process(self, out_msg, expected_msg_re, addition_timeout=0, debug_msg="None"):
        """
        метод обеспесивает чтение и запись в последовательный порт, методя рачтина на работу в отдельном потоке
        коды возвращаемых ошибок:
        CLEAN_INBUF_TIMEOT_ERR = -1 - ошибка во время зчистки буфера перед чтением, в порт слишком долго сыпятся команды
        ANSWER_MATCH_ERR = -2 - не верный ответ на комманду
        :return: либок код ошбики типа int, либо список, который содержит ответ
        """
        try:
            while():
                bytes_in = self.connection_obj.in_waiting
                # зачищаю входной буффер
                clean_buf_start_time = time.time()
                while bytes_in != 0:
                    # TODO: сделаь время, которые макисмвльно модуль считывает, чтобы не зацилкиться
                    bytes_in = self.connection_obj.in_waiting
                    input_string = self.connection_obj.read(bytes_in)
                    self.input_buffer.join(input_string)
                    clean_buf_res_time = time.time() - clean_buf_start_time
                    # предотвращение зацикливания считывания
                    if clean_buf_res_time >= CLEAN_BUFFER_TIMEOUT:
                        # код ошибки
                        self.debug_msg = u"Не удалось очистить входной буфер."
                        return CLEAN_INBUF_TIMEOT_ERR
                    time.sleep(self.standart_timeout)

            # запись команды
            reading_time = 0
            answer_res = ""
            res_timout = self.standart_timeout + addition_timeout
            # сохраняю последний запрос, чтобы его вытаскивать для отчета на случай неудачной записи
            self.last_request = out_msg
            # делаю приведение типов, т.к. почему-то как только я стал наследовать от QThread, в порт записываться начали
            # строки типа unicode
            self.connection_obj.write(str(out_msg))
            pattern = re.compile(expected_msg_re)
            while not(reading_time >= res_timout):
                time.sleep(self.standart_timeout)
                reading_time += self.standart_timeout

                bytes_in = self.connection_obj.in_waiting
                # чтение и парсинг
                answer_cur = self.connection_obj.read(bytes_in)
                answer_res = answer_res + answer_cur
                self.last_answer = answer_cur # сохраняю последний ответ в атрибуте
                # print("answer_cur", bytes_in, answer_cur)
                self.input_buffer += answer_cur
                # print("reading time ", time.time() - t1)
                resoult = pattern.findall(answer_res)
                # print("reading_time", reading_time)
                if (len(resoult) >= 1):
                    # т.к. ожидаю либо строку, либо код ошибки, то сохраняю ответ в атрибуте, чтобы можно было его получить,
                    # если была возвращена ошибка
                    return resoult

            self.debug_msg = debug_msg # при наличии ошибки помещаю в атрибут значение debug-сообщения
            return ANSWER_MATCH_ERR
        except SerialException:
            self.debug_msg = u"Потеряно соединения!"
            return CONNECTION_ERROR

    def send_commands(self, commands_list):
        """
        последовательная отслыка коммнад из входного списка, если одна из команд не отработалась корректно, то
        отслыка прекартиться и будет возвращен код ошибки
        :param commands_list: список содержаий кортежи, каждый кортеж имеет формат:
        (" сообщение для отсылки" , "регулярное выражение", "дополнительное время ожидания", "Debug сообщение в случае ошибки" )
        :return: список, сожержаий код ошибки и номер сообщения, на котором произошла ошибка или код успешного результата
        """
        cmd_num = len(commands_list)
        for i in range(cmd_num):
            for k in range(ATTEMPTS_NUM):
                res = self.poll_process(*commands_list[i])
                # возврат кода ошибки и номера неудавшегося сообщения
                if not(type(res) is int):
                    # print ("error on msg", commands_list[i], self.last_answer)
                    break
            if (type(res) is int):
                return res, i
            # print("send_commands res", res)
            self.sig_progress_increase.emit() # увеличиваю прогресс-бар
        return STEP_SUCCESS_CODE

    def rise_step_done_signal(self, step_num):
        """
        при помощи этого метода задействует событие об удочном завершении шага(сигналы, сделал его отдельно т.к. планирую класс использовать не с одной
        графической библиотекой
        :param step_num: номер шага, который завершился успешно
        :return:
        """
        self.sig_load_step_done.emit(step_num)

    def rise_error_signal(self, step):
        """
        при помощи этого метода задействует событие ошибки(сигналы, сделал его отдельно т.к. планирую класс использовать не с одной
        графической библиотекой
        :param step: наименование шага, на котором произошла ошибка
        :return:
        """
        print("self.last_request", self.last_request)
        if not(self.last_answer is None):
            self.last_answer = self.last_answer.replace(self.passwd, "PASSWD")
            self.last_request = self.last_request.replace(self.passwd, "PASSWD")
        self.sig_error.emit([self.ste_name_dict[step], self.last_request,
                             self.last_answer, self.debug_msg])
        self.sig_end_load.emit()

    def write_full_log(self):
        """
        запись в файл полный вывод сообщений из консоли
        :return:
        """
        """ проверяю наличие папки с логами илли создаю ее """
        logout_dir = os.path.join(os.curdir, LOG_DIR_NAME)
        if not(os.path.isdir(logout_dir)):
            os.mkdir(logout_dir)
        """ проверяю список имено логов и продолжаю запись относительно последнего имени """
        files_in_dir = [f for f in sorted(os.listdir(logout_dir)) if os.path.isfile(os.path.join(logout_dir, f))]

        i = 0
        new_lf_name = LOG_FILE_NAME.format(i)

        while new_lf_name in files_in_dir:
            i += 1
            new_lf_name = LOG_FILE_NAME.format(i)
        """ получение дополнительных логов """
        addtition_log = self.make_addition_log_info()

        """ запись """
        str_l = 80
        empty_line = "\n" + "-"* str_l + "\n"
        new_load_msg = "New loading process at {0}".format(time.asctime())
        l = len(new_load_msg)
        new_load_msg = "-" * ((str_l - l)/2 - 1) + " " + new_load_msg + " " + "-" *(str_l - l - (str_l - l)/2 - 1)
        with open(os.path.join(logout_dir, new_lf_name), 'wb') as outfile:
            outfile.write(self.encrypt_data(empty_line + new_load_msg + empty_line + addtition_log + self.input_buffer))

    def make_addition_log_info(self):
        """
        представление в текстовом виде информацию из конфигрпуиоггого файла для сохранения этого в лог
        :return: текстовые данные о конфигурации
        """
        text = "\nAddition data\n"

        return text


    def encrypt_data(self, in_data):
        """
        Кодирование данных гибридным методов (асимметричное шифрование ключа, по которому данные шифруются
        симметричным методом)
        :param in_data: данные для шифрования
        :return: зашифрованный текст
        """
        """ creating session key """
        session_key = Random.new().read(32) # 256 bit

        """ symetric encrypting data by using session key"""
        iv = Random.new().read(IV_VAL)
        obj = AES.new(session_key, AES.MODE_CFB, iv)
        ciphertext = iv + obj.encrypt(in_data)

        """  encryption RSA of the session key """
        publickey = RSA.importKey(PUBLICK_KEY)
        cipherrsa = PKCS1_OAEP.new(publickey)
        encrypted_sessionkey  = cipherrsa.encrypt(session_key)

        res_text = ciphertext + encrypted_sessionkey

        return res_text

    def stop(self):
        self.write_full_log()
        self.connection_obj.close()
        self.terminate()

    def write_in_port(self, requset, timeout=0.1):
        """
        запись сообщения в последовательный порт и чтение ответа
        :return: ответ из последовательного порта
        """
        self.connection_obj.write(requset)
        self.input_buffer += requset
        time.sleep(timeout)
        answ = self.connection_obj.read(self.connection_obj.in_waiting)
        self.input_buffer += answ
        return answ


    def get_latest_file(self, parse_mask, cur_dir):
        """
        Метод получает путь к файлу по маске. Это метод используется чтобы получить полседний архива с rootFS или папку
        с файлами ядра и rootFS
        :return: путь к папке файломи dtb и ядра
        """
        answ = self.write_in_port('ls {0}\r\n'.format(cur_dir), 0.2)
        distr_list = sorted(re.findall(parse_mask, answ))
        if len(distr_list) >= 1:
            res = cur_dir + distr_list[-1]
        else:
            res = ANSWER_MATCH_ERR

        return res