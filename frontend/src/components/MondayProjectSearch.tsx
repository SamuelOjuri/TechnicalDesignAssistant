import React, { useState } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { RadioGroup, RadioGroupItem } from './ui/radio-group';
import { Label } from './ui/label';
import { Spinner } from './ui/spinner';
import { Alert, AlertTitle, AlertDescription } from './ui/alert';
import { ArrowRight, Building2, RotateCcw, Search } from 'lucide-react';

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
  onReset: () => void;
  embedded?: boolean;
}

export const MondayProjectSearch: React.FC<MondayProjectSearchProps> = ({ 
  apiBaseUrl, 
  projectName, 
  onProjectSelected, 
  onContinueAsNew,
  onReset,
  embedded = false,
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
    <Card className="section-card">
      <CardHeader className="section-header">
        <div className="panel-heading">
          <div>
            <p className="panel-eyebrow">Project matching</p>
            <CardTitle>Email analysis</CardTitle>
            <CardDescription>Confirm whether the enquiry relates to an existing Monday CRM project.</CardDescription>
          </div>
          <span className="assistant-mark" aria-hidden="true"><Search className="h-4 w-4" /></span>
        </div>
      </CardHeader>
      <CardContent className="project-search-content p-5 sm:p-6">
        <div className="extracted-project">
          <span>Extracted project</span>
          <strong><Building2 className="h-4 w-4" aria-hidden="true" /> {projectName}</strong>
        </div>
        
        {isSearching ? (
          <div className="flex items-center justify-center py-10 my-4">
            <Spinner /> 
            <span className="ml-3 text-sm font-semibold text-[#444648]">Searching Monday CRM...</span>
          </div>
        ) : searchResults ? (
          <div className="mt-4">
            {searchResults.exists && searchResults.matches && searchResults.matches.length > 0 ? (
              <>
                <div className="match-list-heading">
                  <strong>Potential matches</strong>
                  <span>{searchResults.matches.length} found</span>
                </div>
                <RadioGroup
                  value={selectedProjectId || ''}
                  onValueChange={(value) => setSelectedProjectId(value)}
                  className="space-y-3"
                >
                  {searchResults.matches.map((match) => (
                    <div key={match.id} className={`project-match ${selectedProjectId === match.id ? 'project-match--selected' : ''}`}>
                      <RadioGroupItem value={match.id} id={`project-${match.id}`} className="mt-1" />
                      <div className="min-w-0 flex-1 ml-3">
                        <Label htmlFor={`project-${match.id}`} className="block text-sm font-bold cursor-pointer">
                          {match.title} <span className="text-[#6b6d70] font-normal">({match.name})</span>
                        </Label>
                        <span className="match-score">{(match.similarity * 100).toFixed(1)}% match</span>
                      </div>
                    </div>
                  ))}
                  <div className={`project-match ${selectedProjectId === 'none' ? 'project-match--selected' : ''}`}>
                    <RadioGroupItem value="none" id="project-none" className="mt-1" />
                    <Label htmlFor="project-none" className="ml-3 text-sm font-bold cursor-pointer">
                      None of these projects - treat as a new enquiry
                    </Label>
                  </div>
                </RadioGroup>
                
                <Alert className="mt-5 border-[#e5d8bd] bg-[#faf4e8]">
                  <AlertTitle className="text-[#6e4c14]">Selection determines the enquiry type</AlertTitle>
                  <AlertDescription className="text-[#7c5718]">
                    An existing project is treated as an amendment and loads its current CRM data.
                  </AlertDescription>
                </Alert>
              </>
            ) : (
              <Alert className="border-[#cfd8d2] bg-[#edf4ef]">
                <AlertTitle className="text-[#2f6547]">No matching projects found</AlertTitle>
                <AlertDescription className="text-[#3f7154]">
                  This will be treated as a new enquiry.
                </AlertDescription>
              </Alert>
            )}
            
            <div className={`project-actions ${embedded ? 'project-actions--embedded' : ''}`}>
              {embedded && (
                <Button
                  onClick={onReset}
                  variant="outline"
                  size="default"
                  className="gap-2"
                >
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                  Start over
                </Button>
              )}
              <Button 
                onClick={handleContinue} 
                variant="tapered"
                size="default"
                disabled={isRetrievingDetails}
                className="gap-2"
              >
                {isRetrievingDetails ? (
                  <>
                    <Spinner className="mr-2 h-4 w-4" />
                    <span>Loading...</span>
                  </>
                ) : (
                  <>Continue <ArrowRight className="h-4 w-4" aria-hidden="true" /></>
                )}
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};