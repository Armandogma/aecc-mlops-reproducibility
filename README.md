# AECC: Dynamic Load Balancing and Fault Tolerance in ML Deployments

This repository contains the reference implementation and reproducible artifacts for the paper:  
**"Dynamic Load Balancing and Fault Tolerance in ML Deployments Using a Process Control Table"**.

It demonstrates the **AECC Architecture**, which uses a centralized Redis-based control table to route inference requests to the least loaded worker in real-time, preventing bottlenecks and ensuring High Availability (HA).

---

##  Project Structure

The repository follows a microservices architecture:

- **`control_module/`**: The central API Gateway and Load Balancer (FastAPI + Redis Logic).
- **`worker_node/`**: Reusable ML Inference container (simulates processing latency).
- **`tests/`**: Load testing scripts (Locust) and result plotting tools.
- **`docker-compose.yml`**: Infrastructure as Code (IaC) to orchestrate the entire cluster.

---

##  Quick Start (Reproducibility)

You can set up the complete experimental environment (Redis + Control Module + 3 Workers) in **one step** using Docker.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose) installed.
- Python 3.8+ (only if you want to run the Locust load generator locally).

### Step 1: Start the System
Open your terminal in the project root and run:

```bash
docker-compose up --build