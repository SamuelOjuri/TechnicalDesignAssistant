# Technical Design Assistant

A full-stack application for extracting and analyzing technical design parameters from emails, PDFs, and other documents. Designed specifically for roofing and insulation projects with Monday.com integration.

## 📋 Features

- **Document Processing**: Extract text from emails (.eml, .msg) and PDF files
- **Parameter Extraction**: Automatically identify key design parameters using AI
- **Monday.com Integration**: Search and retrieve project data from Monday.com boards
- **AI-Powered Chat**: Query extracted data with natural language
- **Export Capability**: Download extracted parameters as Excel files

## 🏗️ Architecture

The application consists of two main components:

### 1. Frontend (React + TypeScript)
- Modern UI built with React 18
- TypeScript for type safety
- Tailwind CSS for styling
- Radix UI components

### 2. Backend (Flask)
- RESTful API for file processing and parameter extraction
- Integration with Monday.com API
- Excel file generation

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+
- Monday.com API token (for integration features)
- Google AI API key (for Generative AI features)

### Installation

#### Backend Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/technical-design-assistant.git
cd technical-design-assistant

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Create a .env file with:
# MONDAY_API_TOKEN=your_monday_token
# GOOGLE_API_KEY=your_google_ai_api_key

# Start the backend server
python wsgi.py
```

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

## 📊 Workflow

1. **Upload Documents**: Submit emails (.eml, .msg) or PDF files containing project information
2. **Process Files**: Extract text and identify project details
3. **Monday.com Check**: (Optional) Search for existing projects in Monday.com
4. **Parameter Extraction**: AI analyzes the content to extract key design parameters
5. **Review & Chat**: Review extracted parameters and ask questions using the AI assistant
6. **Export Data**: Download the parameters as Excel file

## 🔑 Key Parameters Extracted

- Post Code
- Drawing Reference
- Drawing Title
- Revision
- Date Received
- Company
- Contact
- Reason for Change (Amendment or New Enquiry)
- Surveyor
- Target U-Value
- Target Min U-Value
- Fall of Tapered
- Tapered Insulation
- Decking

## 🧩 Integration with Monday.com

The application integrates with Monday.com to:
1. Search for existing projects by name
2. Check if an incoming enquiry is an amendment to an existing project
3. Extract previously saved parameters from Monday.com boards
4. Support the workflow for both new enquiries and amendments

## 🛠️ Development

### Project Structure
