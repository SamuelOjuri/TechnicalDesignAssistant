import React from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { getParameterFormatting } from '../lib/parameter-formatting';
import { Spinner } from './ui/spinner';
import { ArrowRight, Download, FileSearch, RotateCcw } from 'lucide-react';

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
  compact?: boolean;
  onShowValidator?: () => void;
}

export const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ 
  results, 
  sources,
  onReset,
  enquiryType,
  extractedText,
  isLoading = false,
  apiBaseUrl,
  compact = false,
  onShowValidator
}) => {
  if (isLoading) {
    return (
      <Card className="section-card">
        <CardHeader className="section-header">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">Technical analysis</p>
              <CardTitle>Preparing results</CardTitle>
            </div>
            <span className="panel-status panel-status--active">In progress</span>
          </div>
        </CardHeader>
        <CardContent className="results-content">
          <div className="flex flex-col items-center justify-center py-14">
            <Spinner className="mb-4 h-8 w-8" /> 
            <p className="text-sm font-semibold text-[#444648]">Analyzing data and preparing results...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!results) {
    return (
      <Card className="section-card">
        <CardHeader className="section-header">
          <CardTitle>Analysis results</CardTitle>
        </CardHeader>
        <CardContent className="p-6 bg-white">
          <div className="analysis-placeholder">
            <div className="flex flex-col items-center">
              <FileSearch className="h-8 w-8 text-[#8a8b8d] mb-3" aria-hidden="true" />
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

  const renderParameterValue = (key: string, value: string) => {
    const formatting = getParameterFormatting(key, value);

    if (!formatting.tooltip) {
      return <span className={formatting.className}>{formatting.label}</span>;
    }

    return (
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
    );
  };

  const renderSource = (key: string) => {
    const source = sources?.[key];
    if (!source) return null;

    return (
      <span className={`source-badge source-badge--${source.toLowerCase().replace(/\s+/g, '-')}`}>
        {source}
      </span>
    );
  };

  return (
    <Card className="section-card">
      <CardHeader className="section-header">
        <div className="panel-heading">
          <div>
            <p className="panel-eyebrow">Technical analysis</p>
            <CardTitle>Extracted parameters</CardTitle>
          </div>
          {enquiryType && <span className="panel-status panel-status--active">{enquiryType}</span>}
        </div>
      </CardHeader>
      <CardContent className={`results-content ${compact ? 'results-content--compact' : ''}`}>
        {compact ? (
          <dl className="compact-results">
            {Object.entries(results).map(([key, value]) => {
              return (
                <div className="compact-result-row" key={key}>
                  <div className="compact-result-copy">
                    <dt>{key}</dt>
                    <dd>{renderParameterValue(key, value)}</dd>
                  </div>
                  {renderSource(key)}
                </div>
              );
            })}
          </dl>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Parameter</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Source</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(results).map(([key, value]) => (
                <TableRow key={key}>
                  <TableCell className="font-medium">{key}</TableCell>
                  <TableCell>{renderParameterValue(key, value)}</TableCell>
                  <TableCell>{renderSource(key)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <div className={`results-toolbar ${compact ? 'results-toolbar--compact' : ''}`}>
          <Button 
            variant="outline" 
            size="default" 
            onClick={onReset}
            className={compact ? 'results-icon-action' : 'gap-2'}
            title={compact ? 'Start a new enquiry' : undefined}
            aria-label={compact ? 'Start a new enquiry' : undefined}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            <span className={compact ? 'sr-only' : undefined}>New enquiry</span>
          </Button>

          <div className="results-toolbar-actions">
            <Button
              variant="outline"
              size="default"
              onClick={downloadExcel}
              className={compact ? 'results-icon-action' : 'gap-2'}
              title={compact ? 'Export results to Excel' : undefined}
              aria-label={compact ? 'Export results to Excel' : undefined}
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              <span className={compact ? 'sr-only' : undefined}>Export Excel</span>
            </Button>

            {onShowValidator && (
              <Button
                variant="tapered"
                size="default"
                onClick={onShowValidator}
                className="gap-2"
              >
                Review for CRM
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}; 