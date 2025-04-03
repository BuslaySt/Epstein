import time
import pandas as pd
import numpy as np
import ctypes
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok
import matplotlib.pyplot as plt

class Picoscope3204D:
    def __init__(self):
        """
        Initialize the Picoscope device.
        """
        # Create chandle and status ready for use
        self.status = {}
        self.chandle = ctypes.c_int16() # device identifier returned by ps3000aOpenUnit

        # Opens the device/s
        self.status["openunit"] = ps.ps3000aOpenUnit(ctypes.byref(self.chandle), None)

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
        print("Picoscope initialized.")
        
    def initialize_ports(self):
        """
        Initialize the Picoscope ports A and B.
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
        self.channelA_range = ps.PS3000A_RANGE['PS3000A_500MV']
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
        self.channelB_range = ps.PS3000A_RANGE['PS3000A_2V']
        analogue_offset = 0 # 0 V

        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle,
                                                channel,
                                                enabled,
                                                coupling_type,
                                                self.channelB_range,
                                                analogue_offset)
        assert_pico_ok(self.status["setChB"])

    def setup_trigger(self):

        # Sets up simple trigger
        # Handle = Chandle ; device identifier returned by ps3000aOpenUnit
        # Enable = 1 ; zero to disable the trigger; any other value to set the trigger
        # Source = ps3000A_channel_A = 0 ; the channel on which to trigger
        # Threshold = 1024 ADC counts ; the ADC count at which the trigger will fire
        # Direction = ps3000A_Falling = 3 ; the direction in which the signal must move to cause a trigger.
        # Direction = ps3000A_Rising = 2 ; The following directions are supported: ABOVE, BELOW, RISING, FALLING and RISING_OR_FALLING.
        # Delay = 0 ; the time between the trigger occurring and the first sample.
        # autoTrigger_ms = 1000 ; the number of milliseconds the device will wait if no trigger occurs
        self.status["trigger"] = ps.ps3000aSetSimpleTrigger(self.chandle, 1, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'], 0, ps.PS3000A_THRESHOLD_DIRECTION['PS3000A_RISING'], 0, 1000)
        assert_pico_ok(self.status["trigger"])

        print('Trigger set up on chB')

    def setup_generator(self, frequency=50, amplitude=1000000) -> None:
        """
        Set up the signal generator with specified frequency and amplitude.
        """
        # Output a sine wave with peak-to-peak voltage of 2 V and frequency of 10 kHz
        # handle = chandle
        # offsetVoltage = 0
        # pkToPk = 2000000 ; max 2 V
        self.amplitude = amplitude
        # waveType = ctypes.c_int16(0) = PS3000A_SINE
        wavetype = ctypes.c_int16(0)
        # startFrequency = 50 Hz
        # stopFrequency = 50 Hz
        self.frequency = frequency
        # increment = 0
        # dwellTime = 1
        # sweepType = ctypes.c_int16(1) = PS3000A_UP
        sweepType = ctypes.c_int32(0)
        # operation = 0
        # shots = 0
        # sweeps = 0
        # triggerType = ctypes.c_int16(0) = PS3000A_SIGGEN_RISING
        triggertype = ctypes.c_int32(0)
        # triggerSource = ctypes.c_int16(0) = P3000A_SIGGEN_NONE
        triggerSource = ctypes.c_int32(0)
        # extInThreshold = 1
        self.status["SetSigGenBuiltIn"] = ps.ps3000aSetSigGenBuiltIn(self.chandle, 0, self.amplitude, wavetype, self.frequency, self.frequency, 0, 1, sweepType, 0, 4, 0, triggertype, triggerSource, 1)
        assert_pico_ok(self.status["SetSigGenBuiltIn"])

        print(f"Generator set up with {frequency} Hz and {amplitude/1000} mV.")
    
    def read_data(self, max_samples=30000, sample_rate=1252):
        """
        Read data samples from the Pico device.
        """
        # Setting the number of samples to be collected
        preTriggerSamples = 0
        postTriggerSamples = max_samples
        # maxsamples = preTriggerSamples + postTriggerSamples
        self.maxsamples = max_samples

        # Gets timebase infomation
        # WARNING: When using this example it may not be possible to access all Timebases as all channels are enabled by default when opening the scope.  
        # To access these Timebases, set any unused analogue channels to off.
        # Handle = chandle
        # Timebase = 2 = timebase
        # Nosample = maxsamples
        # TimeIntervalNanoseconds = ctypes.byref(timeIntervalns)
        # MaxSamples = ctypes.byref(returnedMaxSamples)
        # Segement index = 0
        self.timebase = sample_rate # 1252 == 10 mks
        timeIntervalns = ctypes.c_float()
        returnedMaxSamples = ctypes.c_int16()
        self.status["GetTimebase"] = ps.ps3000aGetTimebase2(self.chandle, self.timebase, self.maxsamples, ctypes.byref(timeIntervalns), 1, ctypes.byref(returnedMaxSamples), 0)
        assert_pico_ok(self.status["GetTimebase"])

        # Creates a overlow location for data
        overflow = ctypes.c_int16()
        # Creates converted types maxsamples
        cmaxSamples = ctypes.c_int32(self.maxsamples)

        # Starts the block capture
        # Handle = chandle
        # Number of prTriggerSamples
        # Number of postTriggerSamples
        # Timebase = 2 = 4ns (see Programmer's guide for more information on timebases)
        # time indisposed ms = None (This is not needed within the example)
        # Segment index = 0
        # LpRead = None
        # pParameter = None
        self.status["runblock"] = ps.ps3000aRunBlock(self.chandle, preTriggerSamples, postTriggerSamples, self.timebase, 1, None, 0, None, None)
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
        # handle = chandle
        # source = PS3000A_CHANNEL_A = 0
        # pointer to buffer max = ctypes.byref(bufferAMax)
        # pointer to buffer min = ctypes.byref(bufferAMin)
        # buffer length = maxSamples
        # segment index = 0
        # ratio mode = PS3000A_RATIO_MODE_NONE = 0
        # self.status["SetDataBuffers"] = ps.ps3000aSetDataBuffers(self.chandle, 0, ctypes.byref(bufferAMax), ctypes.byref(bufferAMin), maxsamples, 0, 0)
        # assert_pico_ok(self.status["SetDataBuffers"])
        self.status["setDataBuffersA"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                            ctypes.byref(bufferAMax), #bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            self.maxsamples,
                                                            0,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
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

    def check_limits(self, df) -> bool:
        """
        Check if data is within channel limits.
        """
        power_range = { 0  : 10,
                        1  : 20,
                        2  : 50,
                        3  : 100,
                        4  : 200,
                        5  : 500,
                        6  : 1000,
                        7  : 2000,
                        8  : 5000,
                        9  : 10000,
                        10 : 20000}
        if (df.min()['ch_A'] > -power_range[self.channelA_range]) and (df.max()['ch_A'] < power_range[self.channelA_range]) and (df.min()['ch_B'] > -power_range[self.channelB_range]) and (df.max()['ch_B'] < power_range[self.channelB_range]):
            print("В пределах измерений каналов")
            return True
        if (df.min()['ch_A'] <= -power_range[self.channelA_range]) or (df.max()['ch_A'] >= power_range[self.channelA_range]):
            print("выход за пределы измерения канала А")
            return False
        if (df.min()['ch_B'] <= -power_range[self.channelB_range]) or (df.max()['ch_B'] >= power_range[self.channelB_range]):
            print("выход за пределы измерения канала B")    
            return False

    def save_data(self, df: pd.DataFrame):
        """
        Close the Picoscope device.
        """
        filename = time.strftime("%Y-%m-%d_%H-%M")
        df.to_csv(f"rawdata_{filename}_{self.maxsamples}@{self.frequency}Hz_{int(self.amplitude/1000)}mV.csv")

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
    picoscope = Picoscope3204D()
    try:
        picoscope.initialize_ports()
        picoscope.setup_trigger()
        input('Подключите усилитель')
        picoscope.setup_generator(frequency=50, amplitude=1000000)  # 30000 samples at 50 Hz, 1 V, 10 mks
        data = picoscope.read_data(max_samples=20000, sample_rate=1252)
        if picoscope.check_limits(data):
            print(data.head(20))
        else:
            print("Надо увеличить лимиты канала")
        # picoscope.save_data(data)        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        picoscope.close()
