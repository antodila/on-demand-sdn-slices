# On-Demand SDN Slices with Ryu and ComNetsEmu

This project implements an on-demand network slicing system using the Ryu controller and the ComNetsEmu network emulator. The system allows for the dynamic activation and deactivation of network "slices," each with a guaranteed bandwidth (QoS) for specific traffic flows, without disrupting the overall network connectivity.

## Project Architecture

-   **`slicing_controller.py`**: The core of the system. It is a Ryu application that manages the network topology, installs OpenFlow rules for packet forwarding, and orchestrates the application of QoS policies. It exposes a REST API for slice management.
-   **`topology.py`**: A Python script that uses ComNetsEmu to create the virtual network topology, including hosts, switches, and links.
-   **`slices.yaml`**: A YAML configuration file where the slices are defined. For each slice, the traffic flows (source and destination) and the guaranteed bandwidth percentage are specified.
-   **`cli.py`**: A simple command-line interface to interact with the controller's REST API and manage slices.
-   **`queue_create.sh`** & **`queue_delete.sh`**: Bash scripts invoked by the controller to apply and remove QoS rules (`tc` queues and filters) on the switch interfaces.
-   **`requirements.txt`**: A list of the necessary Python dependencies for the project.

## Prerequisites

Ensure the following components are installed on your system (preferably an Ubuntu VM):
1.  **ComNetsEmu**: The network emulator.
2.  **Ryu SDN Controller**: The framework for the controller.
3.  **Python 3** and `pip`.
4.  **Open vSwitch**.

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
*   This command will start ComNetsEmu and open its command-line interface (`mininet>`).

**Terminal 3: Use the CLI to Manage Slices**
This terminal will be used to activate and deactivate slices via the `cli.py` script.

## Functional Test Scenarios

Once the controller and topology are running, you can verify the system.

### 1. Baseline Connectivity Test
In the Mininet CLI (Terminal 2), verify that all hosts can communicate.
```
mininet> pingall
```
**Expected Result:** The test should succeed with `0% dropped`, confirming that the controller's learning switch functionality is working correctly.

### 2. Activate and Verify a Single Slice (QoS)
In Terminal 3, activate the "work" slice.
```bash
./cli.py activate work
```
In Terminal 2, measure the bandwidth between the two hosts in the slice.
```
mininet> iperf h1 h5
```
**Expected Result:** The bandwidth should be limited to approximately **20 Mbits/sec**, as defined in `slices.yaml`.

### 3. Activate Multiple, Isolated Slices
While the "work" slice is active, activate the "gaming" slice in Terminal 3.
```bash
./cli.py activate gaming
```
In Terminal 2, test the bandwidth for both slices.
```
mininet> iperf g1 gs
mininet> iperf h1 h5
```
**Expected Result:** The first test (`g1 -> gs`) should show ~60 Mbits/sec, and the second (`h1 -> h5`) should still show ~20 Mbits/sec, demonstrating that the slices are isolated.

### 4. Deactivate a Slice
In Terminal 3, deactivate the "work" slice.
```bash
./cli.py deactivate work
```
In Terminal 2, verify that the bandwidth for the `h1 -> h5` flow has returned to maximum, while the "gaming" slice remains unaffected.
```
mininet> iperf h1 h5
mininet> iperf g1 gs
```
**Expected Result:** The first test should now show the full link bandwidth (~85-95 Mbits/sec), while the second should remain at ~60 Mbits/sec.

### Cleanup
To exit, type `exit` in the Mininet CLI. Then, run the cleanup command to remove any residual network configurations.
```bash
sudo mn -c
```

## Next Steps and Future Development

To enhance the project and meet the requirements for a two-person group, the next steps will focus on robustness and more advanced test scenarios.

1.  **[COMPLETED] Admission Control:**
    -   **Goal:** The controller must check if the bandwidth required by a new slice is available along the entire path before activating it. If the bandwidth is insufficient, the activation must fail with a clear error message.
    -   **Status:** This functionality is already correctly implemented in `activate_slice` and has been verified through testing. The controller successfully rejects slices that would over-provision a link.

2.  **Fault Tolerance:**
    -   **Goal:** Implement link failure handling. If a link used by an active slice goes down, the controller should attempt to recalculate an alternative path and dynamically reroute the traffic.
    -   **Test Scenario:** Add a redundant link to the topology. Activate a slice, start a long-running `iperf` test, and then bring down the primary link (`link s1 s4 down`). Verify that the traffic recovers on the alternative path.