import React, { useState } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Spinner } from './ui/spinner';

interface FileUploaderProps {
  onUpload: (files: FileList) => void;
  isProcessing: boolean;
  currentFile?: string;
  processingStage?: string;
}

export const FileUploader: React.FC<FileUploaderProps> = ({ 
  onUpload, 
  isProcessing, 
  currentFile,
  processingStage 
}) => {
  const [files, setFiles] = useState<FileList | null>(null);
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(e.target.files);
    }
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (files) {
      onUpload(files);
    }
  };
  
  return (
    <Card className="shadow-md border-0">
      <CardHeader className="bg-[#b82c25] text-white rounded-t-lg">
        <CardTitle>
          <span className="step-indicator">1</span> Upload & Process
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} encType="multipart/form-data">
          <div className="mb-4">
            <div className="border-2 border-dashed border-gray-300 rounded-md p-8 text-center bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer">
              <input
                type="file"
                name="files"
                accept=".eml,.msg,.pdf"
                multiple
                onChange={handleFileChange}
                className="hidden"
                disabled={isProcessing}
                id="file-upload"
              />
              <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <span className="text-base font-medium text-gray-700">Drag & drop files or click to browse</span>
                <span className="text-sm text-gray-500 mt-1">
                  Accepts .eml, .msg, and .pdf files
                </span>
              </label>
              {files && !isProcessing && (
                <div className="mt-4 text-left">
                  <p className="text-sm font-medium text-gray-700">Selected files:</p>
                  <ul className="mt-1 text-sm text-gray-500">
                    {Array.from(files).map((file, index) => (
                      <li key={index} className="truncate">{file.name}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {isProcessing && (
                <div className="mt-6 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="flex items-center mb-2">
                    <Spinner className="mr-3 h-5 w-5" />
                    <span className="font-medium text-gray-800">Processing files...</span>
                  </div>
                  
                  {currentFile && (
                    <div className="mt-2 text-left">
                      <div className="text-sm font-medium text-gray-700 mb-1">
                        {processingStage || 'Processing'}:
                      </div>
                      <div className="p-2 bg-gray-50 rounded border border-gray-200 text-sm">
                        {currentFile.endsWith('.eml') && (
                          <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded text-xs mr-2">EMAIL</span>
                        )}
                        {currentFile.endsWith('.msg') && (
                          <span className="px-1.5 py-0.5 bg-purple-100 text-purple-800 rounded text-xs mr-2">OUTLOOK</span>
                        )}
                        {currentFile.endsWith('.pdf') && (
                          <span className="px-1.5 py-0.5 bg-red-100 text-red-800 rounded text-xs mr-2">PDF</span>
                        )}
                        {currentFile}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          <Button 
            type="submit" 
            variant="tapered"
            size="xl"
            disabled={!files || isProcessing}
          >
            {isProcessing ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing...
              </span>
            ) : (
              "▶️ Process Files"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}; 