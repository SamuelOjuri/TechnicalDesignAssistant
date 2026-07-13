import React, { useEffect, useState } from 'react';
import './styles/globals.css';
import { FileUploader } from './components/FileUploader';
import { ResultsDisplay } from './components/ResultsDisplay';
import { ChatInterface } from './components/ChatInterface';
import { MondayProjectSearch } from './components/MondayProjectSearch';
import { Button } from './components/ui/button';
import { ParameterValidator } from './components/ParameterValidator';
import { Check, ClipboardCheck, FileSearch, HelpCircle, MessageSquareText, RotateCcw, Upload } from 'lucide-react';
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

const useMediaQuery = (query: string) => {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);

  useEffect(() => {
    const mediaQuery = window.matchMedia(query);
    const updateMatches = (event: MediaQueryListEvent) => setMatches(event.matches);

    setMatches(mediaQuery.matches);
    mediaQuery.addEventListener('change', updateMatches);
    return () => mediaQuery.removeEventListener('change', updateMatches);
  }, [query]);

  return matches;
};

// NEW – keep track of where each value was taken from
interface ParameterSource {
  [key: string]: 'Email Content' | 'Monday CRM' | 'Business Rule';
}

const App: React.FC = () => {
  const isEmbedded = new URLSearchParams(window.location.search).get('layout') === 'monday';
  const isCompactAnalysis = useMediaQuery('(max-width: 899px)');
  const isCompactResults = useMediaQuery('(max-width: 560px)');
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
  const [analysisTab, setAnalysisTab] = useState<'parameters' | 'assistant'>('parameters');

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

  const hasUploadedData = Boolean(extractedText || extractedParams || showMondaySearch);
  const hasAnalysisWorkspace = Boolean(extractedParams || isLoadingResults);
  const workflowSteps = [
    {
      label: 'Upload files',
      icon: Upload,
      status: hasUploadedData ? 'complete' : 'current',
    },
    {
      label: 'Review analysis',
      icon: FileSearch,
      status: showParameterValidator
        ? 'complete'
        : hasUploadedData || isLoadingResults
          ? 'current'
          : 'upcoming',
    },
    {
      label: 'Create CRM task',
      icon: ClipboardCheck,
      status: showParameterValidator ? 'current' : 'upcoming',
    },
  ] as const;
  const currentWorkflowIndex = Math.max(
    workflowSteps.findIndex((step) => step.status === 'current'),
    0
  );
  const currentWorkflowStep = workflowSteps[currentWorkflowIndex];
  const CurrentWorkflowIcon = currentWorkflowStep.icon;
  const showAnalysisTabs = isEmbedded && isCompactAnalysis && Boolean(extractedParams);

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
    setAnalysisTab('parameters');
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
    <div className="min-h-screen app-shell flex flex-col" data-layout={isEmbedded ? 'embedded' : 'standalone'}>
      {!isEmbedded && (
        <header className="app-header">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-[68px] flex items-center justify-between gap-4">
            <div className="flex items-center min-w-0">
              <img
                src="/tapered-logo.png"
                alt="TaperedPlus Limited"
                className="h-8 w-auto object-contain flex-none"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
              <span className="hidden sm:block ml-4 pl-4 border-l border-[#d9d9d4] app-title truncate">
                Technical Design Assistant
              </span>
            </div>
            <Button variant="ghost" size="sm" className="gap-2 text-[#444648] hover:bg-[#f4f4f1] hover:text-[#171717]">
              <HelpCircle className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Help</span>
            </Button>
          </div>
        </header>
      )}

      <main className="app-main w-full max-w-7xl mx-auto flex-1 px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        {!isEmbedded && (
          <section className="workspace-intro" aria-labelledby="workspace-title">
            <p className="workspace-eyebrow">TaperedPlus Intelligent Design System</p>
            <div className="workspace-intro-copy">
              <h1 id="workspace-title">Automated Enquiry Processor</h1>
              <p>Transform raw enquiries into verified, CRM-ready technical data.</p>
            </div>
          </section>
        )}

        {isEmbedded ? (
          <nav className="embedded-progress" aria-label="Enquiry processing progress">
            <div className="embedded-progress-summary">
              <span className="embedded-progress-icon" aria-hidden="true">
                <CurrentWorkflowIcon className="h-4 w-4" />
              </span>
              <span className="embedded-progress-copy">
                <span>Step {currentWorkflowIndex + 1} of {workflowSteps.length}</span>
                <strong>{currentWorkflowStep.label}</strong>
              </span>
            </div>
            <div
              className="embedded-progress-track"
              role="progressbar"
              aria-label={`Step ${currentWorkflowIndex + 1} of ${workflowSteps.length}: ${currentWorkflowStep.label}`}
              aria-valuemin={1}
              aria-valuemax={workflowSteps.length}
              aria-valuenow={currentWorkflowIndex + 1}
            >
              {workflowSteps.map((step) => (
                <span key={step.label} className={`embedded-progress-segment embedded-progress-segment--${step.status}`} />
              ))}
            </div>
          </nav>
        ) : (
          <nav className="workflow-stepper" aria-label="Enquiry processing progress">
            <ol>
              {workflowSteps.map((step, index) => {
                const StepIcon = step.icon;
                return (
                  <li key={step.label} className={`workflow-step workflow-step--${step.status}`} aria-current={step.status === 'current' ? 'step' : undefined}>
                    <span className="workflow-step-icon" aria-hidden="true">
                      {step.status === 'complete' ? <Check className="h-4 w-4" /> : <StepIcon className="h-4 w-4" />}
                    </span>
                    <span className="workflow-step-copy">
                      <span>0{index + 1}</span>
                      <strong>{step.label}</strong>
                    </span>
                  </li>
                );
              })}
            </ol>
          </nav>
        )}

        <div className="workflow-content space-y-6 lg:space-y-8">
          {/* {error && (
            <Alert variant="destructive">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )} */}
          
          {(!hasUploadedData || isProcessing) && (
            <section aria-label="Upload enquiry documents">
              <FileUploader
                onUpload={handleFileUpload}
                isProcessing={isProcessing}
                currentFile={currentFile || undefined}
                processingStage={processingStage || undefined}
              />
            </section>
          )}
          
          {showMondaySearch && projectName && (
            <section aria-label="Match enquiry to a project">
              <MondayProjectSearch 
                apiBaseUrl={API_BASE_URL}
                projectName={projectName}
                onProjectSelected={handleProjectSelected}
                onContinueAsNew={handleContinueAsNew}
                onReset={resetApp}
                embedded={isEmbedded}
              />
            </section>
          )}
          
          {hasAnalysisWorkspace && (
            <>
              {showAnalysisTabs && (
                <div className="analysis-tabs" role="tablist" aria-label="Analysis workspace">
                  <button
                    type="button"
                    role="tab"
                    id="parameters-tab"
                    aria-controls="parameters-panel"
                    aria-selected={analysisTab === 'parameters'}
                    className={analysisTab === 'parameters' ? 'analysis-tab--active' : undefined}
                    onClick={() => setAnalysisTab('parameters')}
                  >
                    <FileSearch className="h-4 w-4" aria-hidden="true" />
                    Parameters
                    <span>{Object.keys(extractedParams ?? {}).length}</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    id="assistant-tab"
                    aria-controls="assistant-panel"
                    aria-selected={analysisTab === 'assistant'}
                    className={analysisTab === 'assistant' ? 'analysis-tab--active' : undefined}
                    onClick={() => setAnalysisTab('assistant')}
                  >
                    <MessageSquareText className="h-4 w-4" aria-hidden="true" />
                    Assistant
                  </button>
                </div>
              )}
              <div className={`analysis-workspace ${extractedParams ? 'analysis-workspace--with-chat' : ''}`}>
                <section
                  id="parameters-panel"
                  className="min-w-0"
                  aria-label="Analysis results"
                  aria-labelledby={showAnalysisTabs ? 'parameters-tab' : undefined}
                  hidden={showAnalysisTabs && analysisTab !== 'parameters'}
                >
                  <ResultsDisplay
                    results={extractedParams}
                    sources={paramSources}
                    onReset={resetApp}
                    enquiryType={enquiryType}
                    extractedText={extractedText ?? ''}
                    isLoading={isLoadingResults}
                    apiBaseUrl={API_BASE_URL}
                    compact={isEmbedded && isCompactResults}
                    onShowValidator={canCreateMondayItem ? handleShowValidator : undefined}
                  />
                </section>

                {extractedParams && (
                  <aside
                    id="assistant-panel"
                    className="min-w-0"
                    aria-label="Technical assistant"
                    aria-labelledby={showAnalysisTabs ? 'assistant-tab' : undefined}
                    hidden={showAnalysisTabs && analysisTab !== 'assistant'}
                  >
                    <ChatInterface
                      disabled={false}
                      onSendMessage={handleSendChatMessage}
                      onReset={chatResetTrigger}
                    />
                  </aside>
                )}
              </div>
            </>
          )}

          {showParameterValidator && extractedParams && (
            <ParameterValidator
              extractedParams={validatorParams ?? extractedParams}
              enquiryType={enquiryType}
              apiBaseUrl={API_BASE_URL}
              emailFile={originalEmailFile}
              paramSources={paramSources}
              embedded={isEmbedded}
              onClose={() => {
                setShowParameterValidator(false);
                setValidatorParams(null);
              }}
              onSuccess={() => {
                // Optional: Handle success, maybe show a success message
                // setShowParameterValidator(false);
                // setValidatorParams(null);
              }}
            />
          )}
          
          {hasUploadedData && !extractedParams && !isEmbedded && (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                onClick={resetApp}
                className="gap-2 bg-white text-[#444648] hover:text-[#171717]"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Start new enquiry
              </Button>
            </div>
          )}
        </div>
      </main>

      {!isEmbedded && (
        <footer className="app-footer">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
            <strong>TaperedPlus</strong>
            <span>&copy; {new Date().getFullYear()} TaperedPlus Limited. All rights reserved.</span>
          </div>
        </footer>
      )}
    </div>
  );
};

export default App; 