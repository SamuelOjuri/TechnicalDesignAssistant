import React, { useState, useRef, DragEvent } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Spinner } from './ui/spinner';
import { FileText, Mail, ScanLine, UploadCloud } from 'lucide-react';

interface FileUploaderProps {
  onUpload: (files: FileList) => void;
  isProcessing: boolean;
  currentFile?: string;
  processingStage?: string;
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const FileUploader: React.FC<FileUploaderProps> = ({ 
  onUpload, 
  isProcessing, 
  currentFile,
  processingStage 
}) => {
  const [files, setFiles] = useState<FileList | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  
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

  // Drag event handlers
  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFiles(e.dataTransfer.files);
    }
  };

  const handleBrowseClick = () => {
    if (inputRef.current && !isProcessing) {
      inputRef.current.click();
    }
  };
  
  return (
    <Card className="section-card">
      <CardHeader className="section-header">
        <div className="panel-heading">
          <div>
            <p className="panel-eyebrow">Input documents</p>
            <CardTitle>Upload enquiry files</CardTitle>
            <CardDescription>Import email messages and supporting PDFs for technical analysis.</CardDescription>
          </div>
          <span className="panel-status">Step 01</span>
        </div>
      </CardHeader>
      <CardContent className="upload-content p-5 sm:p-6">
        <form onSubmit={handleSubmit} encType="multipart/form-data">
          <div className="mb-4">
            <div 
              className={`upload-dropzone ${dragActive ? 'upload-dropzone--active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={handleBrowseClick}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  handleBrowseClick();
                }
              }}
              role="button"
              tabIndex={isProcessing ? -1 : 0}
              aria-disabled={isProcessing}
            >
              <input
                ref={inputRef}
                type="file"
                name="files"
                accept=".eml,.msg,.pdf"
                multiple
                onChange={handleFileChange}
                className="hidden"
                disabled={isProcessing}
                id="file-upload"
              />
              <div className="flex flex-col items-center">
                <span className="upload-icon" aria-hidden="true">
                  <UploadCloud className="h-6 w-6" />
                </span>
                <span className="text-sm font-bold text-[#171717]">Drop enquiry files here</span>
                <span className="text-sm text-[#6b6d70] mt-1">or click to browse .eml, .msg, and .pdf files</span>
              </div>
              {files && !isProcessing && (
                <div className="selected-files" onClick={(event) => event.stopPropagation()}>
                  <div className="selected-files-heading">
                    <span>Ready to process</span>
                    <span>{files.length} {files.length === 1 ? 'file' : 'files'}</span>
                  </div>
                  <ul>
                    {Array.from(files).map((file) => {
                      const FileIcon = /\.(eml|msg)$/i.test(file.name) ? Mail : FileText;
                      return (
                        <li key={`${file.name}-${file.lastModified}`}>
                          <FileIcon className="h-4 w-4" aria-hidden="true" />
                          <span className="truncate">{file.name}</span>
                          <span>{formatFileSize(file.size)}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              
              {isProcessing && (
                <div className="processing-state" onClick={(event) => event.stopPropagation()}>
                  <div className="flex items-center mb-2">
                    <Spinner className="mr-3 h-5 w-5" />
                    <span className="font-bold text-[#171717]">Processing files</span>
                  </div>
                  
                  {currentFile && (
                    <div className="mt-2 text-left">
                      <div className="text-sm font-medium text-[#6b6d70] mb-1">
                        {processingStage || 'Processing'}:
                      </div>
                      <div className="processing-file">
                        <span className="file-type-badge">
                          {currentFile.endsWith('.eml') ? 'EMAIL' : currentFile.endsWith('.msg') ? 'OUTLOOK' : 'PDF'}
                        </span>
                        {currentFile}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="upload-actions flex justify-end">
            <Button
              type="submit"
              variant="tapered"
              size="lg"
              disabled={!files || isProcessing}
              className="gap-2 w-full sm:w-auto"
            >
              {isProcessing ? (
                <span className="flex items-center">
                  <Spinner className="mr-2 h-4 w-4" />
                  Processing...
                </span>
              ) : (
                <><ScanLine className="h-4 w-4" aria-hidden="true" /> Process files</>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}; 