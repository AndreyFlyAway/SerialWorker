# SerialWorker
Sending sequences of commands in a serial port, checking validation of response.

SerialWorker based on Pyserial(https://pypi.org/project/pyserial/) and QTread class with QT signals (https://pypi.org/project/PyQt5/).

SerialWorker intended to sending text commands into a serial port, waiting an answer necessary time, checking if the answer matches needed RegExp mask, in case when the answer is incorrect the thread emits a signal.
