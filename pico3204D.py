import time
import pandas as pd
import numpy as np
import ctypes
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok
import matplotlib.pyplot as plt


class Picoscope3204D:
    # Константы для удобства
    CHANNEL_RANGES = {
        0: 10,
        1: 20,
        2: 50,
        3: 100,
        4: 200,
        5: 500,
        6: 1000,
        7: 2000,
        8: 5000,
        9: 10000,
        10: 20000
    }
    
    DEFAULT_SAMPLE_RATE = 1252  # соответствует 10 мкс
    DEFAULT_MAX_SAMPLES = 20000

    def __init__(self):
        """Initialize the Picoscope device."""
        # Create chandle and status ready for use
        self.status = {}
        self.chandle = ctypes.c_int16() # device identifier returned by ps3000aOpenUnit
        self._initialize_device()

    def _initialize_device(self):
        """Internal method to initialize the PicoScope device."""
        # Opens the device
        self.status["openunit"] = ps.ps3000aOpenUnit(ctypes.byref(self.chandle), None)
        
        try:
            assert_pico_ok(self.status["openunit"])
        except Exception as e:
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
                raise RuntimeError(f"Unable to open Picoscope device. Error code: {powerstate} : {e}")
            
            assert_pico_ok(self.status["ChangePowerSource"])
        
        print("Picoscope initialized successfully.")

    def configure_channels(self, channel_a_range=5, channel_b_range=7):
        """
        Configure the Picoscope channels A and B with specified ranges.
        
        Args:
            channel_a_range (int): Range index for channel A (default 5 = ±500mV)
            channel_b_range (int): Range index for channel B (default 7 = ±2V)
        """
        self.channel_a_range = channel_a_range
        self.channel_b_range = channel_b_range
        
        # Configure Channel A
        self._set_channel(
            channel='A',
            enabled=True,
            coupling=ps.PS3000A_COUPLING['PS3000A_DC'],
            range_index=channel_a_range
        )
        
        # Configure Channel B
        self._set_channel(
            channel='B',
            enabled=True,
            coupling=ps.PS3000A_COUPLING['PS3000A_DC'],
            range_index=channel_b_range
        )

    def _set_channel(self, channel, enabled, coupling, range_index):
        """Internal method to configure a single channel."""
        channel_name = f'PS3000A_CHANNEL_{channel.upper()}'
        status_key = f"setCh{channel.upper()}"
        
        self.status[status_key] = ps.ps3000aSetChannel(
            self.chandle,
            ps.PS3000A_CHANNEL[channel_name],
            int(enabled),
            coupling,
            range_index,
            0  # analogue_offset
        )
        assert_pico_ok(self.status[status_key])

    def setup_trigger(self, channel='B', threshold=0, direction='RISING', delay=0, auto_trigger_ms=1000):
        """
        Set up a simple trigger on the specified channel.
        
        Args:
            channel (str): Channel to trigger on ('A' or 'B')
            threshold (int): ADC count threshold for trigger
            direction (str): Trigger direction ('RISING', 'FALLING', etc.)
            delay (int): Delay in samples between trigger and first sample
            auto_trigger_ms (int): Auto-trigger timeout in milliseconds
        """
        channel_name = f'PS3000A_CHANNEL_{channel.upper()}'
        direction_name = f'PS3000A_{direction.upper()}'
        
        self.status["trigger"] = ps.ps3000aSetSimpleTrigger(
            self.chandle,
            1,  # enabled
            ps.PS3000A_CHANNEL[channel_name],
            threshold,
            ps.PS3000A_THRESHOLD_DIRECTION[direction_name],
            delay,
            auto_trigger_ms
        )
        assert_pico_ok(self.status["trigger"])
        
        print(f'Trigger set up on channel {channel} ({direction} at {threshold} ADC counts)')

    def setup_signal_generator(self, frequency=50, amplitude=1000000, 
                              wave_type='SINE', offset_voltage=0, 
                              sweep_type='NONE', trigger_type='NONE'):
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
        self.generator_frequency = frequency
        self.generator_amplitude = amplitude
        
        wave_type_code = ctypes.c_int16(ps.PS3000A_WAVE_TYPE[f'PS3000A_{wave_type.upper()}'])
        sweep_type_code = ctypes.c_int32(ps.PS3000A_SWEEP_TYPE[f'PS3000A_{sweep_type.upper()}'])
        trigger_type_code = ctypes.c_int32(ps.PS3000A_SIGGEN_TRIG_TYPE[f'PS3000A_SIGGEN_{trigger_type.upper()}'])
        
        self.status["SetSigGenBuiltIn"] = ps.ps3000aSetSigGenBuiltIn(
            self.chandle,
            offset_voltage,
            amplitude,
            wave_type_code,
            frequency,
            frequency,  # stop frequency (same as start for no sweep)
            0,  # increment
            1,  # dwell time
            sweep_type_code,
            0,  # operation
            4,  # shots (0 = infinite)
            0,  # sweeps
            trigger_type_code,
            ctypes.c_int32(0),  # triggerSource = NONE
            1   # extInThreshold
        )
        assert_pico_ok(self.status["SetSigGenBuiltIn"])
        
        print(f"Signal generator configured: {frequency} Hz, {amplitude/1000} mV {wave_type.lower()} wave")

    def capture_data(self, max_samples=None, sample_rate=None):
        """
        Capture data from the configured channels.
        
        Args:
            max_samples (int): Number of samples to capture
            sample_rate (int): Sample rate (timebase setting)
            
        Returns:
            pd.DataFrame: DataFrame with time, ch_A and ch_B columns
        """
        max_samples = max_samples or self.DEFAULT_MAX_SAMPLES
        sample_rate = sample_rate or self.DEFAULT_SAMPLE_RATE
        
        # Configure timebase
        time_interval_ns = ctypes.c_float()
        returned_max_samples = ctypes.c_int16()
        
        self.status["GetTimebase"] = ps.ps3000aGetTimebase2(
            self.chandle,
            sample_rate,
            max_samples,
            ctypes.byref(time_interval_ns),
            1,  # oversample
            ctypes.byref(returned_max_samples),
            0   # segment index
        )
        assert_pico_ok(self.status["GetTimebase"])

        # Setup buffers
        buffer_a = (ctypes.c_int16 * max_samples)()
        buffer_b = (ctypes.c_int16 * max_samples)()
        
        self._setup_data_buffers(buffer_a, buffer_b, max_samples)
        
        # Start capture
        self._run_block_capture(max_samples, sample_rate)
        
        # Retrieve data
        samples_read = self._retrieve_data(max_samples)
        
        # Convert to mV
        max_adc = self._get_max_adc_value()
        ch_a_mv = adc2mV(buffer_a, self.channel_a_range, max_adc)
        ch_b_mv = adc2mV(buffer_b, self.channel_b_range, max_adc)
        
        # Create time axis
        time_axis = np.linspace(0, (samples_read - 1) * time_interval_ns.value, samples_read)
        
        return pd.DataFrame({
            'time': time_axis,
            'ch_A': ch_a_mv,
            'ch_B': ch_b_mv
        })

    def _setup_data_buffers(self, buffer_a, buffer_b, max_samples):
        """Internal method to setup data buffers for both channels."""
        self.status["setDataBuffersA"] = ps.ps3000aSetDataBuffers(
            self.chandle,
            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
            ctypes.byref(buffer_a),
            None,
            max_samples,
            0,  # segment index
            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']
        )
        assert_pico_ok(self.status["setDataBuffersA"])
        
        self.status["setDataBuffersB"] = ps.ps3000aSetDataBuffers(
            self.chandle,
            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
            ctypes.byref(buffer_b),
            None,
            max_samples,
            0,  # segment index
            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']
        )
        assert_pico_ok(self.status["setDataBuffersB"])

    def _run_block_capture(self, max_samples, sample_rate):
        """Internal method to start block capture."""
        self.status["runblock"] = ps.ps3000aRunBlock(
            self.chandle,
            0,  # preTriggerSamples
            max_samples,  # postTriggerSamples
            sample_rate,
            1,  # timebase
            None,  # time indisposed ms
            0,  # segment index
            None,  # lpRead
            None  # pParameter
        )
        assert_pico_ok(self.status["runblock"])

    def _retrieve_data(self, max_samples):
        """Internal method to retrieve captured data."""
        # Wait for capture to complete
        ready = ctypes.c_int16(0)
        while not ready.value:
            self.status["isReady"] = ps.ps3000aIsReady(self.chandle, ctypes.byref(ready))
        
        # Get the values
        samples_read = ctypes.c_int32(max_samples)
        overflow = (ctypes.c_int16 * 10)()
        
        self.status["GetValues"] = ps.ps3000aGetValues(
            self.chandle,
            0,  # start index
            ctypes.byref(samples_read),
            0,  # downSampleRatio
            0,  # downSampleRatioMode
            0,  # segment index
            ctypes.byref(overflow)
        )
        assert_pico_ok(self.status["GetValues"])
        
        return samples_read.value

    def _get_max_adc_value(self):
        """Internal method to get the maximum ADC value."""
        max_adc = ctypes.c_int16()
        self.status["maximumValue"] = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(max_adc))
        assert_pico_ok(self.status["maximumValue"])
        return max_adc

    def check_limits(self, data_frame):
        """
        Check if captured data is within channel limits.
        
        Args:
            data_frame (pd.DataFrame): DataFrame with ch_A and ch_B columns
            
        Returns:
            int: 0 if within limits, 1 if channel A out of range, 2 if channel B out of range
        """
        channel_a_limit = self.CHANNEL_RANGES[self.channel_a_range]
        channel_b_limit = self.CHANNEL_RANGES[self.channel_b_range]
        
        ch_a_min = data_frame['ch_A'].min()
        ch_a_max = data_frame['ch_A'].max()
        ch_b_min = data_frame['ch_B'].min()
        ch_b_max = data_frame['ch_B'].max()
        
        if (ch_a_min > -channel_a_limit and ch_a_max < channel_a_limit and 
            ch_b_min > -channel_b_limit and ch_b_max < channel_b_limit):
            print("All channels within measurement range")
            return 0
        
        if ch_a_min <= -channel_a_limit or ch_a_max >= channel_a_limit:
            print(f"Channel A out of range ({ch_a_min:.2f} to {ch_a_max:.2f} mV, limit ±{channel_a_limit} mV)")
            return 1
        
        if ch_b_min <= -channel_b_limit or ch_b_max >= channel_b_limit:
            print(f"Channel B out of range ({ch_b_min:.2f} to {ch_b_max:.2f} mV, limit ±{channel_b_limit} mV)")
            return 2

    def save_data(self, data_frame, frequency=None, amplitude=None):
        """
        Save captured data to CSV file.
        
        Args:
            data_frame (pd.DataFrame): Data to save
            frequency (float): Optional signal generator frequency for filename
            amplitude (float): Optional signal generator amplitude for filename
        """
        timestamp = time.strftime("%Y-%m-%d_%H-%M")
        freq_str = f"@{frequency}Hz" if frequency is not None else ""
        amp_str = f"_{int(amplitude/1000)}mV" if amplitude is not None else ""
        
        filename = f"rawdata_{timestamp}{freq_str}{amp_str}.csv"
        data_frame.to_csv(filename, index=False)
        print(f"Data saved to {filename}")

    def close(self):
        """Close the Picoscope device."""
        self.status["stop"] = ps.ps3000aStop(self.chandle)
        assert_pico_ok(self.status["stop"])
        
        self.status["close"] = ps.ps3000aCloseUnit(self.chandle)
        assert_pico_ok(self.status["close"])
        
        print("Picoscope closed successfully.")


if __name__ == "__main__":
    picoscope = Picoscope3204D()
    try:
        picoscope.configure_channels(channel_a_range=5, channel_b_range=7)  # ±500mV and ±2V
        picoscope.setup_trigger(channel='B', direction='RISING')
        
        input("Connect the amplifier and press Enter to continue...")
        
        picoscope.setup_signal_generator(frequency=50, amplitude=1000000)  # 1V, 50Hz
        data = picoscope.capture_data(max_samples=20000)
        
        if picoscope.check_limits(data) == 0:
            print(data.head())
            picoscope.save_data(data, frequency=50, amplitude=1000000)
        else:
            print("Adjust channel ranges and try again.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        picoscope.close()