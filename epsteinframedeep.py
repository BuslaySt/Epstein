import time
import os
import sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import epscalc
import matplotlib.pyplot as plt
from pico3204D import Picoscope3204D


class EpsteinFrameUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_connections()
        self._initialize_measurement_lists()
        
        # Initialize hardware references
        self.picoscope = None
        
    def _setup_ui(self):
        """Initialize UI components and styles."""
        loadUi("epsdesign.ui", self)
        
        # Apply CSS style
        self._load_stylesheet("epsdesign.css")
        
        # Configuration list
        self.cBox_conf.addItems(['1', '2', '3'])
        
        # Graph settings
        self.graphWidget.setBackground('w')
    
    def _load_stylesheet(self, filename):
        """Load and apply CSS stylesheet."""
        try:
            with open(filename, "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Error loading stylesheet: {e}")
    
    def _setup_connections(self):
        """Setup button event handlers."""
        self.pBtn_init.clicked.connect(self.init_pico)
        self.pBtn_start.clicked.connect(self.start_measurements)
        self.pBtn_save.clicked.connect(self.save_results)
        self.pBtn_clear.clicked.connect(self.clear_interface)
    
    def _initialize_measurement_lists(self):
        """Initialize lists for storing measurement results."""
        self.listOfH = []     # All H values for plotting
        self.listOfB = []     # All B values for plotting
        self.BmaxList = []     # All Bmax values for results table
        self.PowerLossList = []  # All power loss values for results table
    
    def init_pico(self):
        """Initialize Picoscope and configure ports and generator."""
        try:
            if self.picoscope is None:
                self.picoscope = Picoscope3204D()
            
            # Configure ports
            self.limitA = 5  # 500mV for channel A
            self.limitB = 7  # 2V for channel B
            self.picoscope.initialize_ports(
                channelA_range=self.limitA, 
                channelB_range=self.limitB
            )
            
            # Setup generator
            self.freq = self._get_frequency()
            self.amp = 500000  # Initial amplitude in μV (500mV)
            self.picoscope.setup_generator(
                frequency=self.freq, 
                amplitude=self.amp
            )
            
            self._message("Picoscope initialized successfully")
            
        except Exception as e:
            self._message(f"Error initializing Picoscope: {e}")
    
    def start_measurements(self):
        """Start the measurement process."""
        self._message("Starting measurements...")
        
        try:
            # Get parameters from UI
            self.freq = self._get_frequency()
            target_B = self._get_target_induction()
            config_number = int(self.cBox_conf.currentText())
            sample_params = self._get_sample_parameters()
            
            # Initialize hardware
            self.init_pico()
            
            # Clear previous results
            self.lbl_Bmax.clear()
            self.lbl_powerLosses.clear()
            
            # Run measurement process
            self._run_measurement_cycle(target_B, config_number, sample_params)
            
        except Exception as e:
            self._message(f"Measurement error: {e}")
    
    def _run_measurement_cycle(self, target_B, config_number, sample_params):
        """Run the complete measurement cycle to reach target induction."""
        timebase = 127  # 1 μs
        key = 0  # Flag for target induction reached
        step = 0
        amp_increment = 50000
        
        # Initial measurement to check current induction
        Bmax = self._measure_and_calculate(
            timebase, key, config_number, sample_params
        )[0]
        
        # Adjust amplitude if already above target
        if Bmax > target_B:
            self.amp -= amp_increment
            self.picoscope.setup_generator(
                frequency=self.freq, 
                amplitude=self.amp
            )
        
        # Fine-tune amplitude increment based on difference
        amp_increment = self._calculate_amplitude_increment(Bmax, target_B)
        self.amp -= amp_increment
        
        # Main measurement loop
        while (not key) and (self.amp < 4000000) and (step < 50):
            step += 1
            self.amp += amp_increment
            
            # Configure and measure
            self.picoscope.initialize_ports(
                channelA_range=self.limitA, 
                channelB_range=self.limitB
            )
            self.picoscope.setup_generator(
                frequency=self.freq, 
                amplitude=self.amp
            )
            
            # Read data and check limits
            samples = int(50 * 100000 / self.freq)
            self.data = self.picoscope.read_data(
                max_samples=samples, 
                sample_rate=timebase
            )
            time.sleep(0.002)
            
            # Handle channel limits
            if self._handle_channel_limits():
                continue
            
            # Calculate results
            run_params = [
                self.data, 
                self.freq, 
                key, 
                config_number, 
                sample_params
            ]
            result = epscalc.run(run_params)
            Bmax = result[0]
            
            # Adjust increment based on current difference
            amp_increment = self._calculate_amplitude_increment(Bmax, target_B)
            
            # Check if target reached
            if Bmax >= target_B:
                key = 1
        
        # Final measurement with more samples
        self.picoscope.setup_generator(self.freq, amplitude=self.amp)
        samples = int(200 * 100000 / self.freq)
        self.data = self.picoscope.read_data(
            max_samples=samples, 
            sample_rate=timebase
        )
        
        # Final calculation
        run_params = [
            self.data, 
            self.freq, 
            key, 
            config_number, 
            sample_params
        ]
        result = epscalc.run(run_params)
        
        # Store and display results
        self.Bmax = result[0]
        self.H = result[1]
        self.B = result[2]
        self.powerLosses = result[3]
        
        self._display_results()
        self._store_measurement_data()
        self.plot_data()
        
        # Final status message
        if self.Bmax < target_B:
            self._message("Target induction not reached")
        else:
            self._message("Measurement completed successfully")
    
    def _handle_channel_limits(self):
        """Check and handle channel limit violations."""
        limit_status = self.picoscope.check_limits(self.data)
        
        if limit_status == 1:  # Channel A limit
            if self.limitA < 10:
                self.limitA += 1
            else:
                self._message("Channel A limit reached")
                return True
            self.amp -= self.amp_increment
            return True
            
        elif limit_status == 2:  # Channel B limit
            if self.limitB < 10:
                self.limitB += 1
            else:
                self._message("Channel B limit reached")
                return True
            self.amp -= self.amp_increment
            return True
            
        return False
    
    def _measure_and_calculate(self, timebase, key, config_number, sample_params):
        """Perform measurement and calculation."""
        samples = int(50 * 100000 / self.freq)
        self.picoscope.initialize_ports(
            channelA_range=self.limitA, 
            channelB_range=self.limitB
        )
        self.data = self.picoscope.read_data(
            max_samples=samples, 
            sample_rate=timebase
        )
        
        run_params = [
            self.data, 
            self.freq, 
            key, 
            config_number, 
            sample_params
        ]
        return epscalc.run(run_params)
    
    def _calculate_amplitude_increment(self, Bmax, target_B):
        """Calculate appropriate amplitude increment based on difference."""
        difference = abs(target_B - Bmax)
        
        if difference < 0.1:
            increment = self.freq * 10
        elif difference < 0.5:
            increment = self.freq * 50
        elif difference < 1:
            increment = self.freq * 200
        else:
            increment = self.freq * 500
            
        print(f"Increment: {increment/1000} mV")
        return increment
    
    def _get_frequency(self):
        """Get frequency from UI input."""
        return int(self.lEd_f.text().replace(',', '.'))
    
    def _get_target_induction(self):
        """Get target induction from UI input."""
        return float(self.lEd_B.text().replace(',', '.'))
    
    def _get_sample_parameters(self):
        """Get sample parameters from UI inputs."""
        return [
            float(self.lEd_x.text().replace(',', '.')) / 1000,  # Thickness (mm to m)
            float(self.lEd_y.text().replace(',', '.')) / 1000,  # Width (mm to m)
            int(self.lEd_N.text().replace(',', '.')),  # Number of layers
            float(self.lEd_ro.text().replace(',', '.'))  # Material density
        ]
    
    def _display_results(self):
        """Display measurement results in UI."""
        self.lbl_Bmax.setText(f'Induction: {round(self.Bmax, 4)} T')
        self.lbl_powerLosses.setText(f'Losses: {round(self.powerLosses, 4)} W/kg')
    
    def _store_measurement_data(self):
        """Store measurement data for plotting and saving."""
        self.listOfH.append(self.H)
        self.listOfB.append(self.B)
        self.BmaxList.append(round(self.Bmax, 3))
        self.PowerLossList.append(round(self.powerLosses, 3))
    
    def save_results(self):
        """Save measurement results to files."""
        try:
            data_dir = 'data'
            graph_dir = 'graph'
            timestamp = time.strftime("%Y-%m-%d_%H-%M")
            
            # Create directories if they don't exist
            os.makedirs(data_dir, exist_ok=True)
            os.makedirs(graph_dir, exist_ok=True)
            
            # Save raw data
            data_filename = f"rawdata_{timestamp}@{self.freq}Hz_{int(self.amp/1000)}mV.csv"
            self.data.to_csv(os.path.join(data_dir, data_filename))
            
            # Save graph image
            self._save_graph_image(graph_dir, timestamp)
            
            self._message('Data saved successfully')
            self.clear_interface()
            
        except Exception as e:
            self._message(f"Error saving results: {e}")
    
    def _save_graph_image(self, directory, filename):
        """Save the graph as an image file."""
        plt.figure()
        
        # Plot all hysteresis curves
        for H, B in zip(self.listOfH, self.listOfB):
            plt.plot(H, B, linewidth=0.3, color='orange')
        
        # Configure graph appearance
        plt.grid(visible=True, which='both', axis='both', 
                color='grey', linestyle=':', linewidth=0.5)
        plt.xlabel("H")
        plt.ylabel("B")
        
        # Add informational text
        plt.text(
            min(self.H), (self.Bmax - 0.2),
            f'f = {self.freq} Hz, Bmax = {self.Bmax:.3} T, P = {self.powerLosses:.3} W/kg',
            fontsize=7, 
            bbox={'facecolor': 'yellow', 'alpha': 0.2}
        )
        
        plt.text(
            min(self.H), (self.Bmax - 0.4),
            f'Coil configuration #{int(self.cBox_conf.currentText())}',
            fontsize=5, 
            bbox={'facecolor': 'yellow', 'alpha': 0.2}
        )
        
        plt.text(
            min(self.H), (self.Bmax - 0.6),
            f'Number of layers N = {int(self.lEd_N.text().replace(",", "."))}',
            fontsize=5, 
            bbox={'facecolor': 'yellow', 'alpha': 0.2}
        )
        
        # Add results table
        column_labels = ['B', 'P']
        data = list(zip(self.BmaxList, self.PowerLossList))
        tab = plt.table(
            cellText=data,
            colWidths=[0.1]*2,
            colLabels=column_labels,
            colColours=['yellow']*2,
            loc='lower right'
        )
        tab.set_fontsize(10)
        
        # Save figure
        plt.savefig(
            os.path.join(directory, f"{filename}_hister.jpg"), 
            dpi=600
        )
        plt.close()
    
    def plot_data(self):
        """Plot the current measurement data in the UI."""
        styles = {'color': 'black', 'font-size': '12px'}
        
        self.graphWidget.setLabel('left', "B", **styles)
        self.graphWidget.setLabel('bottom', "H", **styles)
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.setXRange(min(self.H), max(self.H))
        self.graphWidget.setYRange(min(self.B), max(self.B))
        self.pltData = self.graphWidget.plot(
            x=self.H, 
            y=self.B, 
            pen='b'
        )
    
    def clear_interface(self):
        """Clear the interface and reset measurement lists."""
        self.graphWidget.clear()
        self.lbl_Bmax.clear()
        self.lbl_powerLosses.clear()
        self._initialize_measurement_lists()
    
    def _message(self, message):
        """Display a message in console and status bar."""
        print(message)
        self.statusBar.showMessage(message)


def main():
    app = QApplication(sys.argv)
    
    try:
        window = EpsteinFrameUI()
        window.show()
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Critical error: {e}")
        
    finally:
        if hasattr(window, 'picoscope') and window.picoscope:
            window.picoscope.close()
            print("Picoscope closed successfully")


if __name__ == "__main__":
    main()