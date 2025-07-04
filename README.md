# On-Demand SDN Slices with Ryu and ComNetsEmu

This project implements an on-demand network slicing system using the Ryu SDN controller and the ComNetsEmu network emulator. The system allows for the dynamic activation and deactivation of network "slices." Each slice provides a guaranteed bandwidth (QoS) and strict traffic isolation for specific flows, without disrupting general network connectivity.

## Project Architecture

-   **`slicing_controller.py`**: The core of the system. A Ryu application that manages network topology, handles slice activation/deactivation via a REST API, and installs OpenFlow rules to enforce slice policies (forwarding, isolation, and QoS).
-   **`topology.py`**: A Python script that uses ComNetsEmu to build the virtual network topology, including hosts, OpenFlow switches, and links with defined bandwidth.
-   **`slices.yaml`**: A YAML configuration file that defines the available slices. Each slice specifies its traffic flows (source/destination hosts), required bandwidth, and priority.
-   **`cli.py`**: A simple command-line interface for interacting with the controller's REST API to easily activate and deactivate slices.
-   **`queue_create.sh`** & **`queue_delete.sh`**: Bash scripts invoked by the controller to apply and remove Linux Traffic Control (`tc`) queueing disciplines on switch interfaces, thereby enforcing the bandwidth limits for each slice.
-   **`requirements.txt`**: A list of the necessary Python dependencies for the project.

## Prerequisites

Ensure the following components are installed on your system (preferably an Ubuntu-based distribution):
1.  **ComNetsEmu**: The network emulator.
2.  **Ryu SDN Controller**: The framework for the controller.
3.  **Python 3** and `pip`.
4.  **Open vSwitch**.

## Installation and Setup

1.  **Clone the repository** or ensure all project files are in the same directory.

2.  **Create and activate a Python virtual environment**:
    ```bash
    python3 -m venv env
    source env/bin/activate
    ```

3.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Make the QoS scripts executable**:
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
*   `sudo -E` is crucial to run with root privileges while preserving the user's environment variables, including the Python virtual environment.

**Terminal 2: Start the Network Topology**
```bash
sudo -E python3 topology.py
```
*   This command will start ComNetsEmu and open its command-line interface (`mininet>`).

**Terminal 3: Use the CLI to Manage Slices**
This terminal will be used to activate and deactivate slices via the `cli.py` script.

## Functional Test Scenarios

Once the controller and topology are running, perform these tests to verify all system functionalities.

### 1. Baseline Connectivity Test
First, confirm that the controller provides basic L2 connectivity for all hosts when no slices are active.
In the Mininet CLI (Terminal 2):
```
mininet> pingall
```
**Expected Result:** The test must succeed with `0% dropped`, confirming the controller's default forwarding is working.

### 2. Slice Activation: Connectivity, Isolation, and QoS
This multi-part test verifies that activating a slice correctly establishes a private, bandwidth-guaranteed tunnel. We will use the "gaming" slice (`g1` <-> `gs`, 60% bandwidth).

1.  **Activate the Slice**
    In Terminal 3, run:
    ```bash
    ./cli.py activate gaming
    ```
    *Expected Controller Log (Terminal 1):* You should see logs indicating FORWARD, REVERSE, and ISOLATION rules being installed, along with QoS being applied.

2.  **Verify Connectivity (Inside the Slice)**
    In Terminal 2, ping the destination host of the slice:
    ```
    mininet> g1 ping gs
    ```
    **Expected Result:** The ping must succeed (`0% dropped`), confirming the forwarding rules are correct.

3.  **Verify Isolation**
    In Terminal 2, attempt to ping a host outside the slice:
    ```
    mininet> g1 ping h1
    ```
    **Expected Result:** The ping must fail (`100% dropped`), confirming the isolation rules are working.

4.  **Verify QoS (Bandwidth Guarantee)**
    In Terminal 2, run an `iperf` test. **First start the server on the destination**, then run the client:
    ```
    mininet> gs iperf -s &
    mininet> g1 iperf -c 10.0.0.8
    ```
    **Expected Result:** The bandwidth reported by `iperf` should be approximately **60 Mbits/sec**.

### 3. Slice Deactivation and Resource Release
This test verifies that deactivating a slice correctly removes all its rules and frees up network resources.

1.  **Deactivate the Slice**
    In Terminal 3, run:
    ```bash
    ./cli.py deactivate gaming
    ```
    *Expected Controller Log (Terminal 1):* You should see logs indicating that flow rules are removed and QoS is cleaned up.

2.  **Verify Isolation is Removed**
    In Terminal 2, repeat the ping from the isolation test:
    ```
    mininet> g1 ping h1
    ```
    **Expected Result:** The ping must now succeed, as the isolation rules have been removed.

3.  **Verify QoS is Removed**
    In Terminal 2, repeat the `iperf` test:
    ```
    mininet> gs iperf -s &
    mininet> g1 iperf -c 10.0.0.8
    ```
    **Expected Result:** The bandwidth should now be the full link capacity (approx. **95-100 Mbits/sec**), as the QoS limit has been removed.

### 4. Admission Control (Bandwidth Check)
This test verifies that the controller rejects a slice if there is not enough bandwidth available on its path. The `gaming` slice (60 Mbps) and `video` slice (50 Mbps) both need to use the `s1-s4` link, which has a 100 Mbps capacity.

1.  **Activate the first slice** (ensure no other slices are active). In Terminal 3:
    ```bash
    ./cli.py activate gaming
    ```
    This should succeed, consuming 60 Mbps on the `s1-s4` link.

2.  **Verify the first slice's QoS in Mininet (Terminal 2)**. This confirms the baseline for the test.
    ```
    mininet> gs iperf -s &
    mininet> g1 iperf -c 10.0.0.8
    ```
    *Expected Result:* Bandwidth should be ~60 Mbits/sec.

3.  **Attempt to activate the conflicting slice (Terminal 3)**.
    ```bash
    ./cli.py activate video
    ```
    **Expected Result:** This command must fail. The CLI should show an error response from the controller (e.g., status 409 Conflict) with a message like `"Insufficient bandwidth on link s1-s4"`.

4.  **Verify that the original slice is unaffected (Terminal 2)**. This proves that the failed activation did not disrupt existing slices.
    ```
    mininet> g1 iperf -c 10.0.0.8
    ```
    *Expected Result:* Bandwidth should still be ~60 Mbits/sec.

### Cleanup
To exit, type `exit` in the Mininet CLI (Terminal 2). Then, run the cleanup command in any terminal to remove residual network configurations.
```bash
sudo mn -c
```

## Authors

-   Antonio Di Lauro, Raffaele Crocco
-   Networking, University of Trento, 2024
