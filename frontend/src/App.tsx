import React, { useState } from 'react';
import './styles/globals.css';
import { FileUploader } from './components/FileUploader';
import { ResultsDisplay } from './components/ResultsDisplay';
import { ChatInterface } from './components/ChatInterface';
import { MondayProjectSearch } from './components/MondayProjectSearch';
import { Button } from './components/ui/button';
import { ParameterValidator } from './components/ParameterValidator';
//import { Alert, AlertTitle, AlertDescription } from './components/ui/alert';

/**
 * During local development we rely on CRA's proxy (see package.json) so the
 * base URL can stay empty.  In production you can pass REACT_APP_API_BASE_URL.
 */
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL ?? '';

interface Parameter {
  [key: string]: string;
}

// Add constants for better maintainability
const TAPEREDPLUS_ASSIGNMENT_TEXT = "To be assigned by TaperedPlus";

// NEW – keep track of where each value was taken from
interface ParameterSource {
  [key: string]: 'Email Content' | 'Monday CRM' | 'Business Rule';
}

const App: React.FC = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [extractedParams, setExtractedParams] = useState<Parameter | null>(null);
  const [extractedText, setExtractedText] = useState<string | null>(null);
  const [emailParams, setEmailParams] = useState<Parameter | null>(null);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [showMondaySearch, setShowMondaySearch] = useState(false);
  const [enquiryType, setEnquiryType] = useState<'New Enquiry' | 'Amendment' | null>(null);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [chatResetTrigger, setChatResetTrigger] = useState<number>(0);
  const [paramSources, setParamSources] = useState<ParameterSource | null>(null); // NEW
  const [showParameterValidator, setShowParameterValidator] = useState(false);
  const [originalEmailFile, setOriginalEmailFile] = useState<File | null>(null);

  // SNAPSHOT for validator params
  const [validatorParams, setValidatorParams] = useState<Parameter | null>(null);

  /**
   * Combine Monday.com params with the ones parsed from the new email.
   * Returns BOTH the merged values and a per-field source map.
   */
  const mergeParameters = (
    monday: Parameter,
    email: Parameter | null
  ): { merged: Parameter; sources: ParameterSource } => {
    // Default: everything comes from Monday.com
    const merged: Parameter = { ...monday };
    const sources: ParameterSource = Object.keys(monday).reduce(
      (acc, k) => ({ ...acc, [k]: 'Monday CRM' }),
      {}
    );

    if (!email) return { merged, sources };

    const overridableParameters = [
      "Email Subject",
      "Date Received",
      "Hour Received",
      "Target U-Value",
      "Target Min U-Value",
      "Fall of Tapered",
      "Tapered Insulation",
      "Decking"
    ];

    const clean = (v?: string) => v?.trim().toLowerCase();
    const isMissing = (v?: string) => {
      if (!v) return true;
      const val = v.trim().toLowerCase();
      return (
        val === "not found" ||
        val === "not provided" ||
        val === "to be assigned by taperedplus"
      );
    };

    Object.entries(email).forEach(([key, value]) => {
      if (overridableParameters.includes(key)) {
        // Special handling for Email Subject - always include if available from email
        if (key === "Email Subject" && !isMissing(value)) {
          merged[key] = value;
          sources[key] = 'Email Content';
        }
        // For other parameters, use existing logic
        else if (
          key !== "Email Subject" &&
          !isMissing(value) &&
          clean(value) !== clean(monday[key])
        ) {
          merged[key] = value;          // email wins
          sources[key] = 'Email Content';
        }
      }
    });

    return { merged, sources };
  };

  const handleFileUpload = async (files: FileList) => {
    setIsProcessing(true);
    // Reset states
    setExtractedParams(null);
    setExtractedText(null);
    setProjectName(null);
    setShowMondaySearch(false);
    setEnquiryType(null);
    
    const formData = new FormData();
    const fileArray = Array.from(files);
    fileArray.forEach(file => {
      formData.append('files', file);
    });
    
    try {
      // Show processing information for each file
      for (let i = 0; i < fileArray.length; i++) {
        const file = fileArray[i];
        setCurrentFile(file.name);
        
        if (file.name.toLowerCase().endsWith('.eml')) {
          setProcessingStage('Extracting email data');
        } else if (file.name.toLowerCase().endsWith('.msg')) {
          setProcessingStage('Extracting Outlook message data');
        } else if (file.name.toLowerCase().endsWith('.pdf')) {
          setProcessingStage('Processing PDF content');
        }
        
        // Add a small delay just to show the processing stage for each file
        if (fileArray.length > 1) {
          await new Promise(resolve => setTimeout(resolve, 800));
        }
      }
      
      setProcessingStage('Sending files and attachments to server');
      
      const response = await fetch(`${API_BASE_URL}/api/process`, {
        method: 'POST',
        body: formData,
        // Don't set Content-Type header - browser will set it with boundary
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'File processing failed');
      }
      
      setProcessingStage('Analyzing extracted data...');
      
      const data = await response.json();
      setExtractedText(data.extractedText);
      
      // Store the extracted parameters but don't display them yet
      const initialParams = data.params;
      setEmailParams(initialParams);          // Store email params for later use
      
      // If we have a project name, show the Monday.com search component
      if (data.projectName) {
        setProjectName(data.projectName);
        setShowMondaySearch(true);
      } else {
        // If no project name, treat as new enquiry immediately
        setEnquiryType('New Enquiry');
        // Set default values for New Enquiry
        const updatedParams = {
          ...initialParams,
          "Reason for Change": "New Enquiry",
          "Drawing Reference": TAPEREDPLUS_ASSIGNMENT_TEXT,
          "Revision": TAPEREDPLUS_ASSIGNMENT_TEXT
        };
        setExtractedParams(updatedParams);

        // NEW – all values originate from email/content
        const emailOnlySources = Object.keys(updatedParams).reduce(
          (acc, k) => ({ 
            ...acc, 
            [k]: (k === "Drawing Reference" || k === "Revision") 
              ? 'Business Rule' as const 
              : 'Email Content' as const 
          }),
          {}
        );
        setParamSources(emailOnlySources);
      }
      
      // Store the original email file
      const emailFile = fileArray.find(
        file => file.name.toLowerCase().endsWith('.eml') || 
                file.name.toLowerCase().endsWith('.msg')
      );
      setOriginalEmailFile(emailFile || null);
      
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsProcessing(false);
      setCurrentFile(null);
      setProcessingStage(null);
    }
  };

  const handleProjectSelected = async (projectId: string | null) => {
    if (projectId === null || projectId === 'none') {
      // User selected "None of the above" or no selection made
      handleContinueAsNew();
    } else {
      // User selected a project - treat as amendment
      setEnquiryType('Amendment');
      setIsLoadingResults(true); // Set loading state while fetching results
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/monday/project/${projectId}`);
        
        if (!response.ok) {
          throw new Error('Failed to get project details');
        }
        
        const data = await response.json();
        if (data && data.params) {
          // Make sure "Reason for Change" is set to "Amendment"
          const mondayParams = {
            ...data.params,
            "Reason for Change": "Amendment"
          };
          
          const { merged: finalParams, sources: finalSources } =
            mergeParameters(mondayParams, emailParams);
          
          setExtractedParams(finalParams);
          setParamSources(finalSources);          // NEW
          
          // Hide the Monday search component after we've loaded the data
          setShowMondaySearch(false);
        } else {
          throw new Error('Invalid response format');
        }
      } catch (error) {
        console.error('Error getting project details:', error);
        alert('An error occurred while retrieving project details.');
        // Fall back to new enquiry if we can't get project details
        handleContinueAsNew();
      } finally {
        setIsLoadingResults(false); // Clear loading state
      }
    }
  };
  
  const handleContinueAsNew = () => {
    setEnquiryType('New Enquiry');
    setIsLoadingResults(true); // Set loading state
    
    // Use the parameters extracted from processing
    if (extractedText) {
      fetch(`${API_BASE_URL}/api/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          extractedText,
          forceEnquiryType: 'New Enquiry'  // Tell backend to force this as new enquiry
        }),
      })
      .then(response => {
        if (response.ok) return response.json();
        throw new Error('Failed to process text');
      })
      .then(data => {
        // Make sure default values are set for New Enquiry
        const updatedParams = {
          ...data.params,
          "Reason for Change": "New Enquiry",
          "Drawing Reference": TAPEREDPLUS_ASSIGNMENT_TEXT,
          "Revision": TAPEREDPLUS_ASSIGNMENT_TEXT
        };
        setExtractedParams(updatedParams);
        setShowMondaySearch(false); // Hide search component

        // NEW – all values originate from email/content
        const emailOnlySources = Object.keys(updatedParams).reduce(
          (acc, k) => ({ 
            ...acc, 
            [k]: (k === "Drawing Reference" || k === "Revision") 
              ? 'Business Rule' as const 
              : 'Email Content' as const 
          }),
          {}
        );
        setParamSources(emailOnlySources);
      })
      .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while processing text data.');
      })
      .finally(() => {
        setIsLoadingResults(false); // Clear loading state
      });
    } else {
      setShowMondaySearch(false);
      setIsLoadingResults(false); // Clear loading state if no extractedText
    }
  };

  const handleSendChatMessage = async (message: string): Promise<string> => {
    try {
      // Make sure extractedText isn't null/undefined 
      // console.log("Sending extractedText:", extractedText ? extractedText.substring(0, 100) : "none");
      
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          params: extractedParams,
          extractedText,
          paramSources,
          enquiryType,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Chat request failed');
      }
      
      const data = await response.json();
      return data.response;
    } catch (error) {
      console.error('Error:', error);
      return 'Sorry, an error occurred while processing your request.';
    }
  };

  // Compute whether validator can be shown (exactly when amendments/new enquiry params shown & loaded)
  const canCreateMondayItem =
    Boolean(extractedParams) &&
    !isLoadingResults &&
    !showMondaySearch;

  // Only allow showValidator when we're ready, and snapshot the params
  const handleShowValidator = () => {
    if (!canCreateMondayItem || !extractedParams) return;
    setValidatorParams(extractedParams);
    setShowParameterValidator(true);
  };

  const resetApp = () => {
    setExtractedParams(null);
    setExtractedText(null);
    setEmailParams(null);
    setParamSources(null);             // NEW
    setProjectName(null);
    setShowMondaySearch(false);
    setEnquiryType(null);
    setShowParameterValidator(false);
    setOriginalEmailFile(null);
    setValidatorParams(null); // also clear snapshot
    // Clear file selection - we need to find the file input element and reset it
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      // @ts-ignore - This is a valid operation but TypeScript doesn't recognize it
      fileInput.value = '';
    }
    
    // Force chat interface to reset by updating a key or trigger prop
    const timestamp = Date.now(); // Create a unique value
    setChatResetTrigger(timestamp);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* TaperedPlus Header */}
      <header className="app-header">
        <div className="container mx-auto px-4 flex items-center">
          {/* Logo on left */}
          <div className="flex-none">
            <img 
              src="/tapered-logo.png" 
              alt="TaperedPlus Limited" 
              className="h-8 w-auto object-contain" 
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }} 
            />
          </div>
          
          {/* Title centered in remaining space */}
          <div className="flex-grow text-center">
            <span className="app-title">Technical Design Assistant</span>
          </div>
          
          {/* Help button on right */}
          <div className="flex-none">
            <Button variant="ghost" className="text-white hover:bg-red-800">Help</Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto py-10 px-4">        
        <div className="space-y-8 max-w-4xl mx-auto">
          {/* {error && (
            <Alert variant="destructive">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )} */}
          
          <div className="section-container">
            <FileUploader 
              onUpload={handleFileUpload} 
              isProcessing={isProcessing} 
              currentFile={currentFile || undefined}
              processingStage={processingStage || undefined}
            />
          </div>
          
          {showMondaySearch && projectName && (
            <div className="section-container">
              <MondayProjectSearch 
                apiBaseUrl={API_BASE_URL}
                projectName={projectName}
                onProjectSelected={handleProjectSelected}
                onContinueAsNew={handleContinueAsNew}
              />
            </div>
          )}
          
          <div className="section-container">
            <ResultsDisplay 
              results={extractedParams} 
              sources={paramSources}
              onReset={resetApp}
              enquiryType={enquiryType}
              extractedText={extractedText ?? ''}
              isLoading={isLoadingResults}
              apiBaseUrl={API_BASE_URL}
              onShowValidator={canCreateMondayItem ? handleShowValidator : undefined}
            />
          </div>
          
          {showParameterValidator && extractedParams && (
            <div className="section-container">
              <ParameterValidator
                extractedParams={validatorParams ?? extractedParams}
                enquiryType={enquiryType}
                apiBaseUrl={API_BASE_URL}
                emailFile={originalEmailFile}
                paramSources={paramSources}
                onSuccess={() => {
                  // Optional: Handle success, maybe show a success message
                  // setShowParameterValidator(false);
                  // setValidatorParams(null);
                }}
              />
            </div>
          )}
          
          <div className="section-container">
            <ChatInterface 
              disabled={!extractedParams} 
              onSendMessage={handleSendChatMessage}
              onReset={chatResetTrigger}
            />
          </div>
          
          <div className="text-center mt-10">
            <Button 
              variant="outline" 
              onClick={resetApp}
              className="mx-auto flex items-center gap-2 bg-white border-gray-300 text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition-all duration-300 px-6 py-2 rounded-md hover:shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Reset App
            </Button>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 py-6 mt-12">
        <div className="container mx-auto px-4 text-center text-gray-600 text-sm">
          &copy; {new Date().getFullYear()} TaperedPlus Limited. All rights reserved.
        </div>
      </footer>
    </div>
  );
};

export default App; 