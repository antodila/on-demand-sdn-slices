# On-Demand SDN Slices with Ryu and Mininet

This project implements an on-demand network slicing system using the Ryu controller and the Containernet network emulator (based on Mininet). The system allows for the dynamic activation and deactivation of network "slices," each with a guaranteed bandwidth (QoS) for specific traffic flows, without disrupting the overall network connectivity.

## Project Architecture

-   **`slicing_controller.py`**: The core of the system. It's a Ryu application that manages the network topology, installs OpenFlow rules, and orchestrates the application of QoS policies. It exposes a REST API for slice activation/deactivation.
-   **`topology.py`**: A Python script that uses Containernet to create the virtual network topology, including hosts, switches, and links.
-   **`slices.yaml`**: A YAML configuration file where the slices are defined. For each slice, the traffic flows (source and destination) and the guaranteed bandwidth capacity are specified.
-   **`cli.py`**: A simple command-line interface to interact with the controller's REST API to activate and deactivate slices.
-   **`queue_create.sh`** & **`queue_delete.sh`**: Bash scripts invoked by the controller to apply and remove QoS rules (`tc` queues and filters) on the switch interfaces.
-   **`requirements.txt`**: A list of the necessary Python dependencies for the project.

## Prerequisites

Before you begin, ensure that the following are installed on your system (preferably an Ubuntu VM):
1.  **Containernet**: The network emulator. Installation via `git` is recommended.
2.  **Ryu SDN Controller**: The framework for the controller.
3.  **Python 3** and `pip`.
4.  **Open vSwitch**: Typically installed along with Containernet.

## Installation and Setup

1.  **Clone the repository** (if applicable) or ensure all project files are in the same directory.

2.  **Create and activate a Python virtual environment**:
    ```bash
    python3 -m venv env
    source env/bin/activate
    ```

3.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Make the Bash scripts executable**:
    ```bash
    chmod +x queue_create.sh
    chmod +x queue_delete.sh
    ```

## Running the Project

The project requires three separate terminals. Ensure you have activated the virtual environment (`source env/bin/activate`) in every terminal where you will run Python scripts.

**Terminal 1: Start the Ryu Controller**

```bash
sudo -E ryu-manager ryu.topology.switches slicing_controller.py
```
*   `sudo -E` is crucial to run the command with root privileges while preserving the user's environment variables, including the Python virtual environment.

**Terminal 2: Start the Network Topology**

```bash
sudo -E python3 topology.py
```
*   This command will start Containernet and open its command-line interface (`mininet>`).

**Terminal 3: Use the CLI to Manage Slices**

This terminal will be used to activate and deactivate slices.

## Testing Procedure

Once the controller and topology are running, you can verify that the system is working correctly.

1.  **Baseline Test (No Active Slices)**
    In the Mininet CLI (Terminal 2), test the bandwidth between two hosts.
    ```
    mininet> iperf h1 h5
    ```
    The result should show the maximum link bandwidth (e.g., ~85 Mbits/sec).

2.  **Activate the "work" Slice**
    In Terminal 3, run:
    ```bash
    ./cli.py activate work
    ```
    In Terminal 2, re-run the test:
    ```
    mininet> iperf h1 h5
    ```
    The bandwidth should now be limited to approximately **20 Mbits/sec**, as defined in `slices.yaml`.

3.  **Activate the "gaming" Slice (Simultaneous Test)**
    In Terminal 3, run:
    ```bash
    ./cli.py activate gaming
    ```
    In Terminal 2, test the bandwidth for the "gaming" slice and verify that the "work" slice is still active:
    ```
    mininet> iperf g1 gs
    mininet> iperf h1 h5
    ```
    The first test should show ~60 Mbits/sec, and the second should show ~20 Mbits/sec.

4.  **Deactivate a Slice**
    In Terminal 3, deactivate the "gaming" slice:
    ```bash
    ./cli.py deactivate gaming
    ```
    In Terminal 2, verify that the bandwidth for `g1 -> gs` has returned to its maximum, while the bandwidth for `h1 -> h5` is still limited.
    ```
    mininet> iperf g1 gs
    mininet> iperf h1 h5
    ```

5.  **Test the "emergency" Slice**
    In Terminal 3, run:
    ```bash
    ./cli.py activate emergency
    ```
    In Terminal 2, start the iperf server on `h3` and run the client on `ps`:
    ```
    mininet> h3 iperf -s &
    mininet> ps iperf -c h3
    ```
    The bandwidth should be limited to approximately **20 Mbits/sec**. To verify, deactivate the slice:
    ```bash
    # In Terminal 3
    ./cli.py deactivate emergency
    ```
    And re-run the test in Mininet to see the bandwidth return to maximum:
    ```
    mininet> ps iperf -c h3
    ```

6.  **Clean Up the Environment**
    To exit, type `exit` in the Mininet CLI. Then, run the cleanup command to remove any residual network configurations:
    ```bash
    sudo mn -c
    ```