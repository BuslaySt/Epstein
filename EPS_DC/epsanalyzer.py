from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QPushButton, QFileDialog, QVBoxLayout, QMessageBox
import numpy as np
from PyQt5.uic import loadUi
#from PyQt5.QtWebEngineWidgets import QWebEngineView
import sys, datetime, time, json

from serial import Serial

import pandas as pd
import time
import scipy as sp
#import threading
from pico3204D import Picoscope3204D
from pyqtgraph import PlotWidget, plot

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("eps_analyzer.ui", self)
        
        #--------------------------------------#
        #basic constants
        self.sampleRate = 50000
        self.duration = 0.02
        self.N = int(self.sampleRate*self.duration)
        self.t = np.linspace(0, self.duration, self.N)
        self.serialData = Serial('COM5', baudrate=115200)
        #--------------------------------------#

        # Окно вывода результатов
        self.Zeroe()
        self.graphWindowList = [self.graphWidget, self.graphWidget_2, self.graphWidget_3, self.graphWidget_4]      
        self.pBtnProcess.clicked.connect(self.Run)
        
        #self.peak_chBox.stateChanged.connect(self.PlusPeak)

        self.graphWidget.setBackground('w')
        self.graphWidget_2.setBackground('w')
        self.graphWidget_3.setBackground('w')
        self.graphWidget_4.setBackground('w')
        self.pBtnClear.clicked.connect(self.ClearInterface)
        #self.pBtnShowGraph.clicked.connect(self.PlotData)

#    def PlusPeak(self):
#        if self.peak_chBox.isChecked():
#            self


    def Run(self):
        attenuationFactor = int(self.sineAtt.text().replace(',','.'))
        xs = np.arange(0, self.N)
        sinewave = self.GenSine(attenuationFactor)
        
        if self.peak_chBox.isChecked():
            peak = self.GenPeak()
            signal = sinewave + peak
        else:
            signal = sinewave
        
        self.PlotData(xs, signal, 0)
        self.FFT_in, self.FFTFreqs_in = self.Fourier(signal)        
        self.PlotData(self.FFTFreqs_in, np.abs(self.FFT_in)*2/self.N, 1)
        self.LoadGen(signal, attenuationFactor)
        self._message('Waveform loaded to Gen')
        self.InitPico()
        voltage = self.picoscope.read_data(max_samples=1000, sample_rate=2502).ch_B
        self.Zeroe()
        self.FFT_out, self.FFTFreqs_out = self.Fourier(voltage)
        self._message('ADC signal received')
        self.PlotData(xs, voltage, 2)
        self.PlotData(self.FFTFreqs_out, np.abs(self.FFT_out)*2/self.N, 3)
        self.picoscope.close()

    def InitPico(self):
        self.picoscope = Picoscope3204D()
        self.picoscope.initialize_ports(channelA_range=10, channelB_range=7)

    def GenSine(self, attenuation):
        sine_freq = int(self.sineF.text().replace(',','.'))
        #sine_amp = int(self.sineAmp.text().replace(',','.'))
        signal = np.sin(2*np.pi*sine_freq*self.t)
        waveform = [int((signal[n]/signal.max())*32767/attenuation) for n in range(0, len(signal))]
        return waveform

    def GenPeak(self):
        size = self.N
        sigma = int(self.peakWidth.text().replace(',','.'))
        position = int(self.peakPos.text().replace(',','.'))
        amplitude = int(self.peakAmp.text().replace(',','.'))
        x = np.arange(size)
        if position > 500:
            amplitude = -amplitude
        arr = amplitude * np.exp(-((x - position) ** 2) / (2 * sigma ** 2))
        return arr

    def LoadGen(self, signal, attenuation):
        #waveform = [int((signal[n]/signal.max())*32767/attenuation) for n in range(0, len(signal))]
    
        for point in signal:
            value = point.to_bytes(2, 'big', signed = 'True')
            self.serialData.write(value)

    def Fourier(self, signal):
        FFT = sp.fft.rfft(signal)
        FFTFreqs = sp.fft.rfftfreq(self.N, 1/self.sampleRate)
        return (FFT, FFTFreqs)

    def Zeroe(self):
        zero = 0
        for n in range(0, self.N):
            value = zero.to_bytes(2, 'big')
            self.serialData.write(value)


    def PlotData(self, xs, ys, plotCounter):
        graphWindow = self.graphWindowList[plotCounter]
        styles = {'color': 'black', 'font-size': '12px'}
        graphWindow.setLabel('left', "Harmonic amp", **styles)
        graphWindow.setLabel('bottom', "Harmonic number", **styles)
        graphWindow.showGrid(x = True, y = True)
        #graphWindow.setLogMode(False, True)
        pen = pg.mkPen(color = 'g', width = 2)
        graphWindow.setXRange(min(xs), max(xs))
        graphWindow.setYRange(min(ys), max(ys))
        graphWindow.plot(x = xs, y = ys, pen = pen)#, symbol = 'o')


    def ClearInterface(self):
        ''' Очистка поля графика и текстовых полей '''
        for window in self.graphWindowList:
            window.clear() # очистка графика
        self.Zeroe()


    def _message(self, message: str):
        ''' Вывод сообщений в консоль и статусбар '''
        print(message)
        self.statusBar.showMessage(message)

if __name__ == '__main__':
    # from PyQt5.QtWebEngineWidgets import QWebEngineView # IP: нашел рекомендацию этот импорт делать тут
    # app = QApplication(sys.argv)
    app = QApplication([])
    
    epsanalyzer = MainUI()
    epsanalyzer.show()
    
    # app.exec_()
    sys.exit(app.exec_())