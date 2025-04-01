import time
import pandas as pd
import numpy as np
import ctypes
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok

class Picoscope3204D:
    def __init__(self, sample_rate=1252, max_samples=30000, frequency=50, amplitude=1000000):
        # self.device = {}
        # self.channel_a = 0 # channel_a = PS3000A_CHANNEL_A = 0
        # self.channel_b = 1 # channel_b = PS3000A_CHANNEL_B = 1
        self.sample_rate = sample_rate  # 1252 = 10 mks
        self.max_samples = max_samples
        self.frequency = frequency
        self.amplitude = amplitude
        
    def initialize_ports(self):
        """
        Initialize the Picoscope device and ports A and B.
        """
        # Create chandle and status ready for use
        self.status = {}
        self.chandle = ctypes.c_int16() # == chandle

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
                self.status["ChangePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, 282)
                # If the powerstate is the same as 286 then it will run this if statement
            elif powerstate == 286:
                # Changes the power input to "PICO_USB3_0_DEVICE_NON_USB3_0_PORT"
                self.status["ChangePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, 286)
            else:
                raise RuntimeError("Unable to open Picoscope device.")
        assert_pico_ok(self.status["ChangePowerSource"])
        print("Picoscope initialized.")

        # Set up channel A

        # handle = chandle
        channel = ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'] # = 0
        enabled = 1
        coupling_type = ps.PS3000A_COUPLING['PS3000A_DC'] # = PS3000A_DC == 1
        # range = PS3000A_2V = 7 ; PS3000A_10V = 8
        self.channelA_range = ps.PS3000A_RANGE['PS3000A_500MV'] # ==
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
        self.channelB_range = ps.PS3000A_RANGE['PS3000A_1V']
        analogue_offset = 0 # 0 V

        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle,
                                                channel,
                                                enabled,
                                                coupling_type,
                                                self.channelB_range,
                                                analogue_offset)
        assert_pico_ok(self.status["setChB"])

    def setup_trigger(self, source="a", direction="rising"):

        # Sets up simple trigger
        # Handle = Chandle ; device identifier returned by ps3000aOpenUnit
        # Enable = 1 ; zero to disable the trigger; any other value to set the trigger
        # Source = ps3000A_channel_A = 0 ; the channel on which to trigger
        # Threshold = 1024 ADC counts ; the ADC count at which the trigger will fire
        # Direction = ps3000A_Falling = 3 ; the direction in which the signal must move to cause a trigger.
        # Direction = ps3000A_Rising = 2 ; The following directions are supported: ABOVE, BELOW, RISING, FALLING and RISING_OR_FALLING.
        # Delay = 0 ; the time between the trigger occurring and the first sample.
        # autoTrigger_ms = 1000 ; the number of milliseconds the device will wait if no trigger occurs
        self.status["trigger"] = ps.ps3000aSetSimpleTrigger(self.chandle, 1, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'], 0, ps.PS3000A_THRESHOLD_DIRECTION['PS3000A_RISING'], 0, 1000)
        assert_pico_ok(self.status["trigger"])

        print('Trigger set up')

    def setup_generator(self, frequency=50, amplitude=1000000) -> None:
        """
        Set up the signal generator with specified frequency and amplitude.
        """
        # Output a sine wave with peak-to-peak voltage of 2 V and frequency of 10 kHz
        # handle = chandle
        # offsetVoltage = 0
        # pkToPk = 2000000 ; max 2 V
        # waveType = ctypes.c_int16(0) = PS3000A_SINE
        # startFrequency = 50 Hz
        # stopFrequency = 50 Hz
        # increment = 0
        # dwellTime = 1
        # sweepType = ctypes.c_int16(1) = PS3000A_UP
        # operation = 0
        # shots = 0
        # sweeps = 0
        # triggerType = ctypes.c_int16(0) = PS3000A_SIGGEN_RISING
        # triggerSource = ctypes.c_int16(0) = P3000A_SIGGEN_NONE
        # extInThreshold = 1
        wavetype = ctypes.c_int16(0)
        sweepType = ctypes.c_int32(0)
        triggertype = ctypes.c_int32(0)
        triggerSource = ctypes.c_int32(0)

        self.status["SetSigGenBuiltIn"] = ps.ps3000aSetSigGenBuiltIn(self.chandle, 0, 1000000, wavetype, 50, 50, 0, 1, sweepType, 0, 4, 0, triggertype, triggerSource, 1)
        assert_pico_ok(self.status["SetSigGenBuiltIn"])

        print(f"Generator set up with {frequency} Hz and {amplitude/1000} mV.")
    
    def read_data(self):
        """
        Read data from the generator.
        """
        # Setting the number of sample to be collected
        preTriggerSamples = 0
        postTriggerSamples = 30000
        maxsamples = preTriggerSamples + postTriggerSamples

        # Gets timebase infomation
        # WARNING: When using this example it may not be possible to access all Timebases as all channels are enabled by default when opening the scope.  
        # To access these Timebases, set any unused analogue channels to off.
        # Handle = chandle
        # Timebase = 2 = timebase
        # Nosample = maxsamples
        # TimeIntervalNanoseconds = ctypes.byref(timeIntervalns)
        # MaxSamples = ctypes.byref(returnedMaxSamples)
        # Segement index = 0
        timebase = 1252 # 10 mks
        timeIntervalns = ctypes.c_float()
        returnedMaxSamples = ctypes.c_int16()
        self.status["GetTimebase"] = ps.ps3000aGetTimebase2(self.chandle, timebase, maxsamples, ctypes.byref(timeIntervalns), 1, ctypes.byref(returnedMaxSamples), 0)
        assert_pico_ok(self.status["GetTimebase"])

        # Creates a overlow location for data
        overflow = ctypes.c_int16()
        # Creates converted types maxsamples
        cmaxSamples = ctypes.c_int32(maxsamples)

        # Starts the block capture
        # Handle = chandle
        # Number of prTriggerSamples
        # Number of postTriggerSamples
        # Timebase = 2 = 4ns (see Programmer's guide for more information on timebases)
        # time indisposed ms = None (This is not needed within the example)
        # Segment index = 0
        # LpRead = None
        # pParameter = None
        self.status["runblock"] = ps.ps3000aRunBlock(self.chandle, preTriggerSamples, postTriggerSamples, timebase, 1, None, 0, None, None)
        assert_pico_ok(self.status["runblock"])

        # Create buffers ready for assigning pointers for data collection
        # bufferAMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
        # bufferBMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)

        # Create buffers ready for assigning pointers for data collection
        bufferAMax = (ctypes.c_int16 * maxsamples)()
        # bufferAMin = (ctypes.c_int16 * maxsamples)() # used for downsampling
        bufferBMax = (ctypes.c_int16 * maxsamples)()
        # bufferBMin = (ctypes.c_int16 * maxsamples)() # used for downsampling


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
                                                            maxsamples,
                                                            0,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersA"])

        # Set data buffer location for data collection from channel B
        # source = PS3000A_CHANNEL_B = 1
        self.status["setDataBuffersB"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                            ctypes.byref(bufferBMax), #bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            maxsamples,
                                                            0,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])

        # Creates a overlow location for data
        overflow = (ctypes.c_int16 * 10)()
        # Creates converted types maxsamples
        cmaxSamples = ctypes.c_int32(maxsamples)

        # Checks data collection to finish the capture
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

        df = pd.DataFrame({'Time (ns)' : time_axis, 'Channel A, mV' : adc2mVChAMax, 'Channel B, mV' : adc2mVChBMax})

        return df

        # Start the data collection
        total_samples = self.max_samples
        ps3000.run_block(self.device, total_samples)
        
        # Wait for the block to complete
        ready = ctypes.c_int16()
        while ready.value == 0:
            ps3000.is_ready(self.device, ctypes.byref(ready))
        
        # Retrieve voltage data
        channel_a_data = np.zeros(total_samples, dtype=np.int16)
        channel_b_data = np.zeros(total_samples, dtype=np.int16)
        
        ps3000.get_values(self.device, total_samples, 0, 0, 0, channel_a_data, 0, 0)
        ps3000.get_values(self.device, total_samples, 0, 1, 0, channel_b_data, 0, 0)
        
        # Create a Pandas DataFrame
        time = np.linspace(0, total_samples / self.sample_rate, total_samples)
        data = {
            'Time (s)': time,
            'Channel A': channel_a_data,
            'Channel B': channel_b_data
        }
        
        return pd.DataFrame(data)
    
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
        input('Подключите усилитель')
        picoscope.setup_generator(frequency=50, amplitude=1000000)  # 50 Hz and 1 V
        data = picoscope.read_data()
        print(data.head(20))
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        picoscope.close()