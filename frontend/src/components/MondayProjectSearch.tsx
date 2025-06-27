import React, { useState } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { RadioGroup, RadioGroupItem } from './ui/radio-group';
import { Label } from './ui/label';
import { Spinner } from './ui/spinner';
import { Alert, AlertTitle, AlertDescription } from './ui/alert';

interface ProjectMatch {
  id: string;
  title: string;
  name: string;
  similarity: number;
}

interface SearchResults {
  exists: boolean;
  matches: ProjectMatch[];
}

interface MondayProjectSearchProps {
  apiBaseUrl: string;
  projectName: string | null;
  onProjectSelected: (projectId: string | null) => void;
  onContinueAsNew: () => void;
}

export const MondayProjectSearch: React.FC<MondayProjectSearchProps> = ({ 
  apiBaseUrl, 
  projectName, 
  onProjectSelected, 
  onContinueAsNew 
}) => {
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [isRetrievingDetails, setIsRetrievingDetails] = useState(false);

  const searchProjects = async () => {
    if (!projectName) return;
    
    setIsSearching(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/monday/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ project_name: projectName }),
      });
      
      if (!response.ok) {
        throw new Error('Project search failed');
      }
      
      const data = await response.json();
      setSearchResults(data);
      
      // If there are matches, select the first one by default
      if (data.exists && data.matches && data.matches.length > 0) {
        setSelectedProjectId(data.matches[0].id);
      } else {
        // If no matches, set to "none"
        setSelectedProjectId('none');
      }
    } catch (error) {
      console.error('Error searching projects:', error);
      alert('An error occurred while searching for projects.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleContinue = async () => {
    if (selectedProjectId === 'none') {
      // User selected "None of the above" - treat as new enquiry
      onContinueAsNew();
    } else if (selectedProjectId) {
      // User selected a project - treat as amendment and get details
      setIsRetrievingDetails(true);
      try {
        onProjectSelected(selectedProjectId);
      } catch (error) {
        console.error('Error getting project details:', error);
        alert('An error occurred while retrieving project details.');
      } finally {
        setIsRetrievingDetails(false);
      }
    }
  };

  // Auto-search when projectName changes
  React.useEffect(() => {
    const doSearch = async () => {
      if (projectName) {
        await searchProjects();
      }
    };
    
    doSearch();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectName]);

  if (!projectName) {
    return null;
  }

  return (
    <Card className="shadow-md border-0 mb-8">
      <CardHeader className="bg-[#b82c25] text-white rounded-t-lg section-header">
        <CardTitle className="flex items-center">
          <span className="text-xl">Email Analysis & Project Matching</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2">Extracted Project Name:</h3>
          <p className="text-lg font-medium bg-gray-100 p-3 rounded">{projectName}</p>
        </div>
        
        {isSearching ? (
          <div className="flex items-center justify-center py-6 my-4">
            <Spinner /> 
            <span className="ml-2 text-gray-600">Searching for similar projects in Monday.com...</span>
          </div>
        ) : searchResults ? (
          <div className="mt-4">
            {searchResults.exists && searchResults.matches && searchResults.matches.length > 0 ? (
              <>
                <h3 className="text-lg font-semibold mb-4">Matching Projects Found in Monday.com</h3>
                <RadioGroup
                  value={selectedProjectId || ''}
                  onValueChange={(value) => setSelectedProjectId(value)}
                  className="space-y-3"
                >
                  {searchResults.matches.map((match) => (
                    <div key={match.id} className="flex items-start p-3 border rounded-md hover:bg-gray-50">
                      <RadioGroupItem value={match.id} id={`project-${match.id}`} className="mt-1" />
                      <div className="ml-3">
                        <Label htmlFor={`project-${match.id}`} className="text-base font-medium cursor-pointer">
                          {match.title} <span className="text-gray-600 font-normal">({match.name})</span>
                        </Label>
                        <p className="text-sm text-gray-500">
                          Similarity: {(match.similarity * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                  ))}
                  <div className="flex items-start p-3 border rounded-md hover:bg-gray-50">
                    <RadioGroupItem value="none" id="project-none" className="mt-1" />
                    <Label htmlFor="project-none" className="ml-3 text-base font-medium cursor-pointer">
                      None of the above - Treat as new enquiry
                    </Label>
                  </div>
                </RadioGroup>
                
                <Alert className="mt-6 bg-amber-50 border-amber-200">
                  <AlertTitle className="text-amber-800">Please select a project and click 'Continue' to proceed</AlertTitle>
                  <AlertDescription className="text-amber-700">
                    Selecting a matching project will treat this as an amendment and load data from Monday.com.
                  </AlertDescription>
                </Alert>
              </>
            ) : (
              <Alert className="bg-blue-50 border-blue-200">
                <AlertTitle className="text-blue-800">No matching projects found in Monday.com</AlertTitle>
                <AlertDescription className="text-blue-700">
                  This will be treated as a new enquiry.
                </AlertDescription>
              </Alert>
            )}
            
            <div className="flex justify-end mt-6">
              <Button 
                onClick={handleContinue} 
                variant="tapered"
                size="default"
                disabled={isRetrievingDetails}
              >
                {isRetrievingDetails ? (
                  <>
                    <Spinner className="mr-2 h-4 w-4" />
                    <span>Loading...</span>
                  </>
                ) : (
                  "Continue"
                )}
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};