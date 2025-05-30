import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Spinner } from './ui/spinner';
import { MONDAY_COLUMN_MAPPING, MONDAY_BOARD_CONFIG } from '../lib/monday-columns';

// Add date formatting functions
const formatDateForDisplay = (dateString: string): string => {
  if (!dateString) return '';
  
  // If already in YYYY-MM-DD format, convert to DD/MM/YYYY for display
  const yyyyMmDdRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (yyyyMmDdRegex.test(dateString)) {
    const [year, month, day] = dateString.split('-');
    return `${day}/${month}/${year}`;
  }
  
  return dateString;
};

const formatDateForMonday = (dateString: string): string => {
  if (!dateString) return '';
  
  // Parse DD/MM/YYYY or DD-MM-YYYY format
  const ddMmYyyyRegex = /^(\d{2})[/-](\d{2})[/-](\d{4})$/;
  const match = dateString.match(ddMmYyyyRegex);
  if (match) {
    const [, day, month, year] = match;
    return `${year}-${month}-${day}`;
  }
  
  // If already in YYYY-MM-DD format, return as-is
  const yyyyMmDdRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (yyyyMmDdRegex.test(dateString)) {
    return dateString;
  }
  
  return dateString;
};

// Add value cleaning function
const cleanExtractedValue = (value: string): string => {
  if (!value) return '';
  
  // Remove patterns like ': value' or '": "value",' to just 'value'
  // First try to match pattern with quotes around value
  const quotedMatch = value.match(/["']?\s*:\s*["']([^"']+)["']/);
  if (quotedMatch) {
    return quotedMatch[1].trim();
  }
  
  // Then try to match pattern where colon appears at the start (after optional quotes/whitespace)
  // But not if it looks like a time format (digits:digits)
  const colonMatch = value.match(/^["']?\s*:\s*(.+?)[\s,]*$/);
  if (colonMatch && !value.match(/^\d+:\d+/)) {
    return colonMatch[1].trim();
  }
  
  // If no pattern matches, just strip quotes and whitespace
  return value.replace(/^["'\s]+|["'\s,]+$/g, '');
};

interface ValidatableParameter {
  key: string;
  displayName: string;
  value: string;
  mondayColumnTitle: string;
  editable: boolean;
}

interface ParameterValidatorProps {
  extractedParams: Record<string, string> | null;
  enquiryType: 'New Enquiry' | 'Amendment' | null;
  apiBaseUrl: string;
  onSuccess?: () => void;
}

export const ParameterValidator: React.FC<ParameterValidatorProps> = ({
  extractedParams,
  enquiryType,
  apiBaseUrl,
  onSuccess
}) => {
  const [parameters, setParameters] = useState<ValidatableParameter[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!extractedParams) return;

    // Define the subset of parameters to validate using column titles
    const validatableParams: ValidatableParameter[] = [
      {
        key: 'Date Received',
        displayName: 'Date Received',
        value: cleanExtractedValue(extractedParams['Date Received'] || ''),
        mondayColumnTitle: MONDAY_COLUMN_MAPPING['Date Received'],
        editable: true
      },
      {
        key: 'Hour Received',
        displayName: 'Hour Received',
        value: cleanExtractedValue(extractedParams['Hour Received'] || ''),
        mondayColumnTitle: MONDAY_COLUMN_MAPPING['Hour Received'],
        editable: true
      },
      {
        key: 'Post Code',
        displayName: 'Post Code',
        value: cleanExtractedValue(extractedParams['Post Code'] || ''),
        mondayColumnTitle: MONDAY_COLUMN_MAPPING['Post Code'],
        editable: true
      }
    ];

    // Add Drawing Reference (TP Ref) for amendments
    if (enquiryType === 'Amendment' && extractedParams['Drawing Reference']) {
      // Extract numeric part before first underscore
      const cleanedDrawingRef = cleanExtractedValue(extractedParams['Drawing Reference']);
      const tpRef = cleanedDrawingRef.split('_')[0];
      
      // Only add if we have a valid TP Ref value
      if (tpRef && tpRef !== 'Not provided' && tpRef !== 'Not found') {
        validatableParams.push({
          key: 'Drawing Reference',
          displayName: 'TP Ref',
          value: tpRef,
          mondayColumnTitle: MONDAY_COLUMN_MAPPING['Drawing Reference'],
          editable: false // Not editable since it's derived
        });
      }
    }

    setParameters(validatableParams);
  }, [extractedParams, enquiryType]);

  const handleParameterChange = (index: number, newValue: string) => {
    const updated = [...parameters];
    updated[index].value = newValue;
    setParameters(updated);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      // Prepare the data for Monday.com using column titles
      const columnValuesByTitle = parameters.reduce((acc, param) => {
        let value = param.value;
        
        // Format date values to YYYY-MM-DD before sending
        if (param.key === 'Date Received' && value) {
          value = formatDateForMonday(value);
        }
        
        acc[param.mondayColumnTitle] = value;
        return acc;
      }, {} as Record<string, string>);

      // Clean the email subject for the item name
      const emailSubject = extractedParams?.['Email Subject'] || '';
      const cleanedItemName = cleanExtractedValue(emailSubject) || 'New Item';

      const itemData = {
        board_id: MONDAY_BOARD_CONFIG.boardId,
        group_id: MONDAY_BOARD_CONFIG.groupId,
        item_name: cleanedItemName,
        column_values_by_title: columnValuesByTitle
      };

      console.log('Sending to Monday.com:', itemData); // Debug log

      const response = await fetch(`${apiBaseUrl}/api/monday/create-item`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(itemData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to create Monday CRM item');
      }

      const result = await response.json();
      setSuccess(`Successfully created item in Monday CRM with ID: ${result.id}`);
      
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!extractedParams) {
    return null;
  }

  return (
    <Card className="shadow-md border-0">
      <CardHeader className="bg-[#b82c25] text-white rounded-t-lg">
        <CardTitle>
          Validate Parameters for Item Creation 
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        {success && (
          <Alert className="mb-4 bg-green-50 border-green-200">
            <AlertDescription className="text-green-800">{success}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-4">
          <div className="mb-4 p-3 bg-blue-50 rounded-md">
            <p className="text-sm text-blue-700">
              The following parameters will be used for item creation in the Project Holding Page of Monday CRM:
            </p>
          </div>

          {parameters.map((param, index) => (
            <div key={param.key} className="flex items-center space-x-4">
              <label className="w-32 font-medium text-sm">
                {param.displayName}:
              </label>
              {param.editable ? (
                <Input
                  value={param.value}
                  onChange={(e) => handleParameterChange(index, e.target.value)}
                  className="flex-1"
                  disabled={isSubmitting}
                />
              ) : (
                <span className="flex-1 px-3 py-2 bg-gray-100 rounded-md text-sm">
                  {param.value}
                </span>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-between">
          <Button
            variant="outline"
            disabled={isSubmitting}
            onClick={() => {
              setError(null);
              setSuccess(null);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="tapered"
            onClick={handleSubmit}
            disabled={isSubmitting || parameters.length === 0}
          >
            {isSubmitting ? (
              <>
                <Spinner className="w-4 h-4 mr-2" />
                Creating Item...
              </>
            ) : (
              'Create Monday CRM Item'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};