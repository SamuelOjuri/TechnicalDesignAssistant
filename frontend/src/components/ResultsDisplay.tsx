import React from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { getParameterFormatting } from '../lib/parameter-formatting';
import { Spinner } from './ui/spinner';

interface Parameter {
  [key: string]: string;
}

interface ParameterSource {
  [key: string]: 'Email Content' | 'Monday CRM' | 'Business Rule';
}

interface ResultsDisplayProps {
  results: Parameter | null;
  sources: ParameterSource | null;
  onReset: () => void;
  enquiryType: 'New Enquiry' | 'Amendment' | null;
  extractedText: string;
  isLoading?: boolean;
  apiBaseUrl: string;
}

export const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ 
  results, 
  sources,
  onReset,
  enquiryType,
  extractedText,
  isLoading = false,
  apiBaseUrl
}) => {
  if (isLoading) {
    return (
      <Card className="shadow-md border-0">
        <CardHeader className="bg-[#b82c25] text-white rounded-t-lg">
          <CardTitle>
            <span className="step-indicator">2</span> Analysis Results
          </CardTitle>
        </CardHeader>
        <CardContent className="results-content">
          <div className="flex flex-col items-center justify-center py-8">
            <Spinner className="mb-4 h-8 w-8" /> 
            <p className="text-gray-600">Analyzing data and preparing results...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!results) {
    return (
      <Card className="shadow-md border-0">
        <CardHeader className="bg-[#b82c25] text-white rounded-t-lg">
          <CardTitle>
            <span className="step-indicator">2</span> Analysis Results
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6 bg-white">
          <div className="border-2 border-dashed border-gray-300 rounded-md p-8 text-center bg-gray-50 hover:bg-gray-100 transition-colors">
            <div className="flex flex-col items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-base font-medium text-gray-700">Upload and process files to see analysis results here.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const downloadExcel = () => {
    fetch(`${apiBaseUrl}/api/download-excel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        params: results,
        llm_response: extractedText
      }),
    })
      .then(response => {
        if (!response.ok) {
          throw new Error('Download failed');
        }
        return response.blob();
      })
      .then(blob => {
        // Create a URL for the blob
        const url = window.URL.createObjectURL(blob);
        
        // Create a download link and trigger it
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Technical_Parameters.xlsx';
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        window.URL.revokeObjectURL(url);
        a.remove();
      })
      .catch(error => {
        console.error('Error downloading Excel:', error);
        alert('An error occurred while downloading the Excel file.');
      });
  };

  return (
    <Card className="shadow-md border-0 section-card">
      <CardHeader className="bg-[#b82c25] text-white rounded-t-lg">
        <CardTitle>
          <span className="step-indicator">2</span> Analysis Results {enquiryType && `(${enquiryType})`}
        </CardTitle>
      </CardHeader>
      <CardContent className="results-content">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Parameter</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(results).map(([key, value]) => {
              const formatting = getParameterFormatting(key, value);
              return (
                <TableRow key={key}>
                  <TableCell className="font-medium">{key}</TableCell>
                  <TableCell>
                    {formatting.tooltip ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className={formatting.className}>{formatting.label}</span>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{formatting.tooltip}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : (
                      <span className={formatting.className}>{formatting.label}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {sources?.[key] ?? ''}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <div className="mt-4 flex justify-between">
          <Button variant="tapered" size="default" onClick={downloadExcel}>Download as Excel</Button>
          <Button 
            variant="outline" 
            size="default" 
            onClick={onReset}
            className="bg-gradient-to-r from-blue-50 to-blue-100 border-blue-200 text-blue-600 hover:from-blue-100 hover:to-blue-200 transition-all duration-300 hover:shadow-md"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Process New Files
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}; 