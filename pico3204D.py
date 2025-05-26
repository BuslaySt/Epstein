import time
import pandas as pd
import numpy as np
import ctypes
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok
import matplotlib.pyplot as plt

class Picoscope3204D:
    # Константы для удобства
    POWER_RANGE = { 0  : 10,    # нет такого
                    1  : 20,    # нет такого
                    2  : 50,
                    3  : 100,
                    4  : 200,
                    5  : 500,
                    6  : 1000,
                    7  : 2000,
                    8  : 5000,
                    9  : 10000,
                    10 : 20000}
    
    DEFAULT_SAMPLE_RATE = 1252  # соответствует 10 мкс
    DEFAULT_MAX_SAMPLES = 20000
    
    def __init__(self):
        """
        Initialize the Picoscope device.
        """
        # Create chandle and status ready for use
        self.status = {}
        self.chandle = ctypes.c_int16() # device identifier returned by ps3000aOpenUnit

        # Opens the device
        self.status["openunit"] = ps.ps3000aOpenUnit(ctypes.byref(self.chandle), None)

        # Проверка питания по USB
        try:
            assert_pico_ok(self.status["openunit"])
        except:
            # powerstate becomes the status number of openunit
            powerstate = self.status["openunit"]
            # If powerstate is the same as 282 then it will run this if statement
            if powerstate == 282:
                # Changes the power input to "PICO_POWER_SUPPLY_NOT_CONNECTED"
                print("PICO_POWER_SUPPLY_NOT_CONNECTED")
                self.status["ChangePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, 282)
                # If the powerstate is the same as 286 then it will run this if statement
            elif powerstate == 286:
                # Changes the power input to "PICO_USB3_0_DEVICE_NON_USB3_0_PORT"
                print("PICO_USB3_0_DEVICE_NON_USB3_0_PORT")
                self.status["ChangePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, 286)
            else:
                raise RuntimeError("Unable to open Picoscope device.")
            assert_pico_ok(self.status["ChangePowerSource"])
        print("Picoscope initialized successfully.")
        
    def initialize_ports(self, channelA_range=2, channelB_range=4):
        """
        Configure the Picoscope channels A and B with specified ranges.
        
        Args:
            channel_A_range (int): Range index for channel A (default 5 = ±500mV)
            channel_B_range (int): Range index for channel B (default 7 = ±2V)
        """
        # Set up channel A
        # handle = chandle
        channel = ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'] # = 0
        enabled = 1
        coupling_type = ps.PS3000A_COUPLING['PS3000A_DC'] # = PS3000A_DC == 1
        # 0  == PS3000A_10MV:  ±10 mV - нет
        # 1  == PS3000A_20MV:  ±20 mV - нет
        # 2  == PS3000A_50MV:  ±50 mV
        # 3  == PS3000A_100MV: ±100 mV
        # 4  == PS3000A_200MV: ±200 mV
        # 5  == PS3000A_500MV: ±500 mV
        # 6  == PS3000A_1V:    ±1 V
        # 7  == PS3000A_2V:    ±2 V
        # 8  == PS3000A_5V:    ±5 V
        # 9  == PS3000A_10V:   ±10 V
        # 10 == PS3000A_20V:   ±20 V
        self.channelA_range = channelA_range #ps.PS3000A_RANGE['PS3000A_500MV']
        analogue_offset = 0 # 0 V

        self.status["setChA"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                enabled,
                                                coupling_type,
                                                self.channelA_range,
                                                analogue_offset)
        assert_pico_ok(self.status["setChA"])

        # Set up channel B
        # handle = chandle
        channel = ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'] # == 1
        enabled = 1
        coupling_type = ps.PS3000A_COUPLING['PS3000A_DC'] # = PS3000A_DC == 1
        self.channelB_range = channelB_range # ps.PS3000A_RANGE['PS3000A_2V']
        analogue_offset = 0 # 0 V

        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle,
                                                channel,
                                                enabled,
                                                coupling_type,
                                                self.channelB_range,
                                                analogue_offset)
        assert_pico_ok(self.status["setChB"])

    def setup_trigger(self, enable=1, channel='B', threshold=0, direction='RISING', delay=0, auto_trigger_ms=1000):
        """
        Set up a simple trigger on the specified channel.
        
        Args:
            source (str): Channel to trigger on ('A' or 'B')
            threshold (int): ADC count threshold for trigger
            direction (str): Trigger direction ('RISING', 'FALLING', 'RISING_LOWER', 'OUTSIDE', etc.)
            delay (int): Delay in samples between trigger and first sample
            auto_trigger_ms (int): Auto-trigger timeout in milliseconds
        """
        # Handle = Chandle ; device identifier returned by ps3000aOpenUnit
        # Enable = 1 # zero to disable the trigger; any other value to set the trigger
        # Source = ps3000A_channel_B = 1 ; the channel on which to trigger
        channel_name = f'PS3000A_CHANNEL_{channel.upper()}'
        source = ps.PS3000A_CHANNEL[channel_name]
        # Threshold = 1024 ADC counts ; the ADC count at which the trigger will fire
        # Direction = ps3000A_Falling = 3 ; the direction in which the signal must move to cause a trigger.
        # Direction = ps3000A_Rising = 2 ; The following directions are supported: ABOVE, BELOW, RISING, FALLING and RISING_OR_FALLING.
        threshold_direction = ps.PS3000A_THRESHOLD_DIRECTION[f'PS3000A_{direction}']
        # Delay = 0 ; the time between the trigger occurring and the first sample.
        # autoTrigger_ms = 1000 ; the number of milliseconds the device will wait if no trigger occurs
        self.status["trigger"] = ps.ps3000aSetSimpleTrigger(self.chandle, enable, source, threshold, threshold_direction, delay, auto_trigger_ms)
        assert_pico_ok(self.status["trigger"])

        print(f'Триггер подключен на канале {channel} ({direction} @ {threshold} ADC counts)')

    def setup_generator(self, frequency=50, amplitude=1000000) -> None:
        """
        Set up the built-in signal generator.
        
        Args:
            frequency (float): Output frequency in Hz
            amplitude (int): Peak-to-peak amplitude in microvolts
            wave_type (str): Waveform type ('SINE', 'SQUARE', etc.)
            offset_voltage (int): DC offset voltage in microvolts
            sweep_type (str): Sweep type ('UP', 'DOWN', 'UPDOWN', 'NONE')
            trigger_type (str): Trigger type ('RISING', 'FALLING', 'NONE')
        """
        # Output a sine wave with peak-to-peak voltage of 2 V and frequency of 10 kHz
        self.amplitude = amplitude
        wavetype = ctypes.c_int16(0)
        self.frequency = frequency
        sweepType = ctypes.c_int32(0)
        triggertype = ctypes.c_int32(0)
        triggerSource = ctypes.c_int32(0)
        self.status["SetSigGenBuiltIn"] = ps.ps3000aSetSigGenBuiltIn(
            self.chandle,       # handle = chandle
            0,                  # offsetVoltage = 0 V
            self.amplitude,     # pkToPk = +-2000000 μV ; max +-2 V
            wavetype,           # waveType = ctypes.c_int16(0) = PS3000A_SINE
            self.frequency,     # startFrequency, Hz, the frequency that the signal generator will initially produce
            self.frequency,     # stopFrequency, Hz, the frequency at which the sweep reverses direction or returns to the initial frequency
            0,                  # increment = 0, the amount of frequency increase or decrease in sweep mode
            1,                  # dwellTime = 1, the time for which the sweep stays at each frequency, in seconds
            sweepType,          # sweepType = ctypes.c_int16(1) = PS3000A_UP
            0,                  # operation = 0 = PS3000A_ES_OFF, normal signal generator operation specified by wavetype.
            0,                  # shots = 0: sweep the frequency as specified by sweeps
            0,                  # sweeps = 0: produce number of cycles specified by shots
            triggertype,        # triggerType = ctypes.c_int16(0) = PS3000A_SIGGEN_RISING
            triggerSource,      # triggerSource = ctypes.c_int16(0) = P3000A_SIGGEN_NONE
            1                   # extInThreshold = 1
        )
        assert_pico_ok(self.status["SetSigGenBuiltIn"])

        print(f"Generator set up with {frequency} Hz and {amplitude/1000} mV.")

    def stop_generator(self) -> None:
        """
        Stops the built-in signal generator and the oscilloscope.
        """
        # Stops the scope
        # Handle = chandle
        self.status["stop"] = ps.ps3000aStop(self.chandle)
        assert_pico_ok(self.status["stop"])
        print(f"Oscilloscope stopped.")

    def read_data(self, max_samples=DEFAULT_MAX_SAMPLES, sample_rate=DEFAULT_SAMPLE_RATE) -> pd.DataFrame:
        """
        Read data samples from the Pico device.
        
        Args:
            max_samples (int): Number of samples to capture
            sample_rate (int): Sample rate (timebase setting)
            
        Returns:
            pd.DataFrame: DataFrame with time, ch_A and ch_B columns
        """
        # Setting the number of samples to be collected
        preTriggerSamples = 0
        postTriggerSamples = max_samples
        # maxsamples = preTriggerSamples + postTriggerSamples
        self.maxsamples = max_samples

        # Gets timebase infomation
        # Nosample = maxsamples
        # TimeIntervalNanoseconds = ctypes.byref(timeIntervalns)
        # MaxSamples = ctypes.byref(returnedMaxSamples)
        # Segement index = 0
        self.timebase = sample_rate # 1252 == 10 mks
        timeIntervalns = ctypes.c_float()
        returnedMaxSamples = ctypes.c_int16()
        self.status["GetTimebase"] = ps.ps3000aGetTimebase2(
            self.chandle,                   # Handle = chandle
            self.timebase,                  # Timebase = 2 = timebase
            self.maxsamples,                # No of samples
            ctypes.byref(timeIntervalns),   # TimeIntervalNanoseconds, a pointer to the time interval between readings at the selected timebase. NULL
            1,                              # oversample, not used
            ctypes.byref(returnedMaxSamples), # maxSamples, on exit, the maximum number of samples available. NULL
            0                               # segmentIndex, the index of the memory segment to use
        )
        assert_pico_ok(self.status["GetTimebase"])

        # Creates a overlow location for data
        overflow = ctypes.c_int16()
        # Creates converted types maxsamples
        cmaxSamples = ctypes.c_int32(self.maxsamples)

        # Starts the block capture
        self.status["runblock"] = ps.ps3000aRunBlock(
            self.chandle,       # Handle = chandle
            preTriggerSamples,  # Number of prTriggerSamples
            postTriggerSamples, # Number of postTriggerSamples
            self.timebase,      # Timebase = 2 = 4ns
            1,                  # oversample, not used
            None,               # time indisposed ms = None
            0,                  # segmentIndex = 0, zero-based, specifies which memory segment to use
            None,               # LpRead = None
            None                # pParameter = None
        )
        assert_pico_ok(self.status["runblock"])

        # Create buffers ready for assigning pointers for data collection
        # bufferAMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
        # bufferBMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)

        # Create buffers ready for assigning pointers for data collection
        bufferAMax = (ctypes.c_int16 * self.maxsamples)()
        # bufferAMin = (ctypes.c_int16 * self.maxsamples)() # used for downsampling
        bufferBMax = (ctypes.c_int16 * self.maxsamples)()
        # bufferBMin = (ctypes.c_int16 * self.maxsamples)() # used for downsampling


        # Set data buffer location for data collection from channel A

        # pointer to buffer max = ctypes.byref(bufferAMax)
        # pointer to buffer min = ctypes.byref(bufferAMin)
        
        # self.status["SetDataBuffers"] = ps.ps3000aSetDataBuffers(self.chandle, 0, ctypes.byref(bufferAMax), ctypes.byref(bufferAMin), maxsamples, 0, 0)
        # assert_pico_ok(self.status["SetDataBuffers"])
        self.status["setDataBuffersA"] = ps.ps3000aSetDataBuffers(self.chandle,                         # handle = chandle
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],    # source = PS3000A_CHANNEL_A = 0
                                                            ctypes.byref(bufferAMax),                   #bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            self.maxsamples,                            # buffer length = maxSamples
                                                            0,                                          # segment index = 0
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'] # ratio mode = PS3000A_RATIO_MODE_NONE = 0
        )
        assert_pico_ok(self.status["setDataBuffersA"])

        # Set data buffer location for data collection from channel B
        # source = PS3000A_CHANNEL_B = 1
        self.status["setDataBuffersB"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                            ctypes.byref(bufferBMax), #bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            self.maxsamples,
                                                            0,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])

        # Creates a overlow location for data
        overflow = (ctypes.c_int16 * 10)()
        # Creates converted types maxsamples
        cmaxSamples = ctypes.c_int32(self.maxsamples)

        # Checks data collection to finish the capture
        # Wait for the block to complete
        ready = ctypes.c_int16(0)
        check = ctypes.c_int16(0)
        while ready.value == check.value:
            self.status["isReady"] = ps.ps3000aIsReady(self.chandle, ctypes.byref(ready))

        # Handle = chandle
        # start index = 0
        # noOfSamples = ctypes.byref(cmaxSamples)
        # DownSampleRatio = 0
        # DownSampleRatioMode = 0
        # SegmentIndex = 0
        # Overflow = ctypes.byref(overflow)

        self.status["GetValues"] = ps.ps3000aGetValues(self.chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
        assert_pico_ok(self.status["GetValues"])

        # Finds the max ADC count
        # Handle = chandle
        # Value = ctype.byref(maxADC)
        maxADC = ctypes.c_int16()
        self.status["maximumValue"] = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(maxADC))
        assert_pico_ok(self.status["maximumValue"])

        # Converts ADC from channel A to mV
        adc2mVChAMax =  adc2mV(bufferAMax, self.channelA_range, maxADC)
        adc2mVChBMax = adc2mV(bufferBMax, self.channelB_range, maxADC)

        # Creates the time data
        time_axis = np.linspace(0, (cmaxSamples.value - 1) * timeIntervalns.value, cmaxSamples.value)

        # Plots the data from channel A onto a graph
        # plt.plot(time_axis, adc2mVChAMax[:])
        # plt.plot(time_axis, adc2mVChBMax[:])
        # plt.xlabel('Time (ns)')
        # plt.ylabel('Voltage (mV)')
        # plt.show()

        # data = dict()
        # data['timestamp'] = time_axis
        # data['ch_a'] = adc2mVChAMax
        # data['ch_b'] = adc2mVChBMax

        df = pd.DataFrame({'time' : time_axis, 'ch_A' : adc2mVChAMax, 'ch_B' : adc2mVChBMax})

        return df

    def check_limits(self, df) -> int:
        """
        Проверка, что измеренные напряжения укладываются в диапазон каналов.
        
        Args:
            df (pd.DataFrame): DataFrame with ch_A and ch_B columns
            
        Returns:
            int: 0 if within limits, 1 if channel A out of range, 2 if channel B out of range
        """
        ch_A_lim = self.POWER_RANGE[self.channelA_range]
        ch_B_lim = self.POWER_RANGE[self.channelB_range]

        ch_A_max = df['ch_A'].abs().max()
        ch_B_max = df['ch_B'].abs().max()

        if (ch_A_max < ch_A_lim) and (ch_B_max < ch_B_lim):
            print("В пределах измерений каналов")
            return 0
        if ch_A_max >= ch_A_lim:
            print("выход за пределы измерения канала А")
            return 1
        if ch_B_max >= ch_B_lim:
            print("выход за пределы измерения канала B")    
            return 2

    def save_data(self, df: pd.DataFrame, frequency="", amplitude=""):
        """
        Save captured data to CSV file.
        
        Args:
            df (pd.DataFrame): Data to save
            frequency (float): Optional signal generator frequency for filename
            amplitude (float): Optional signal generator amplitude for filename
        """
        filename = time.strftime("%Y-%m-%d_%H-%M")
        df.to_csv(f"rawdata_{filename}@{frequency}Hz_{int(amplitude/1000)}mV.csv")

    def close(self):
        """
        Close the Picoscope device.
        """
        # Stops the scope
        # Handle = chandle
        self.status["stop"] = ps.ps3000aStop(self.chandle)
        assert_pico_ok(self.status["stop"])

        # Closes the unit
        # Handle = chandle
        self.status["close"] = ps.ps3000aCloseUnit(self.chandle)
        assert_pico_ok(self.status["close"])

        # Displays the status returns
        print(self.status)
        print("Picoscope closed.")

if __name__ == "__main__":
    try:
        picoscope = Picoscope3204D()
        picoscope.initialize_ports(channelA_range=5, channelB_range=7)
        # picoscope.setup_trigger()
        # input('Подключите усилитель')
        # picoscope.setup_generator(frequency=50, amplitude=1000000)  # 30000 samples at 50 Hz, 1 V, 10 mks
        # data = picoscope.read_data()
        # print(picoscope.check_limits(data))
        # match picoscope.check_limits(data):
        #     case 0: print(data.head(20))
        #     case 1: print("Надо увеличить лимиты канала A")
        #     case 2: print("Надо увеличить лимиты канала B")
        # picoscope.save_data(data)
        picoscope.setup_generator(frequency=1, amplitude=1)
        picoscope.stop_generator()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        picoscope.close()
