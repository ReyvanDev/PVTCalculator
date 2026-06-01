# PVT Calculator

A desktop-based Petroleum Fluid Properties Calculator built with Python, Tkinter, and Matplotlib.  
This application helps estimate oil, gas, and water PVT properties using commonly used petroleum engineering correlations.

## Overview

PVT Calculator is designed as a practical tool for petroleum engineering students and reservoir engineering analysis.  
The application provides a graphical interface for calculating reservoir fluid properties, comparing correlations, generating property tables, and visualizing results through charts.

## Features

### Oil Properties
- Bubble point pressure estimation
- Solution gas-oil ratio, Rs
- Oil formation volume factor, Bo
- Oil density
- Dead oil, live oil, and undersaturated oil viscosity
- Oil compressibility
- Saturated and undersaturated condition indicator
- Correlation comparison:
  - Standing
  - Vasquez-Beggs
  - Petrosky-Farshad

### Gas Properties
- Pseudocritical pressure and temperature
- Reduced pressure and reduced temperature
- Gas Z-factor calculation
- Gas formation volume factor, Bg
- Gas density
- Gas viscosity
- Gas compressibility
- Z-factor methods:
  - Dranchuk-Abou-Kassem
  - Hall-Yarborough

### Water Properties
- Water formation volume factor, Bw
- Water density
- Water viscosity
- Dissolved gas in water, Rsw
- Water compressibility

### Property Tables and Charts
- Generate PVT property tables over a pressure range
- Plot pressure vs selected PVT properties
- Export calculation table to CSV

## Tech Stack

- Python
- Tkinter
- Matplotlib

## Installation

Clone this repository:

```bash
git clone https://github.com/yourusername/pvt-calculator.git
cd pvt-calculator

## Installation

Clone this repository:

```bash
git clone https://github.com/ReyvanDev/pvt-calculator.git
cd pvt-calculator
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment:

For Windows:

```bash
.venv\Scripts\activate
```

For macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python src/pvt_calculator.py
```
