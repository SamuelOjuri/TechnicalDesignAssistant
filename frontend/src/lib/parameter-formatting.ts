export interface ParameterFormatting {
  label: string;
  tooltip?: string;
  className?: string;
}

export function cleanValue(value: string): string {
  if (!value) return value;
  
  // Remove JSON-like formatting artifacts
  return value
    // Remove leading quotes, colons
    .replace(/^["':]\s*/, '')
    // Remove trailing quotes, commas
    .replace(/[",;]\s*$/, '')
    // Remove remaining quotes
    .replace(/"/g, '')
    // Handle specific ": " pattern
    .replace(/^:\s*/, '');
}

export function getParameterFormatting(key: string, value: string): ParameterFormatting {
  // Clean the value first
  const cleanedValue = cleanValue(value);
  
  // Default formatting with cleaned value
  const defaultFormat: ParameterFormatting = {
    label: cleanedValue,
  };

  switch (key) {
    case "Post Code":
      if (cleanedValue.length <= 2 && cleanedValue !== "Not found" && cleanedValue !== "Not provided") {
        return {
          label: cleanedValue,
          tooltip: "Showing post code area (first part of postal code)",
          className: "font-semibold"
        };
      }
      break;
      
    case "Tapered Insulation":
      // Add styling for mapped insulation values
      const mappedValues = [
        "TissueFaced PIR", 
        "TorchOn PIR", 
        "FoilFaced PIR", 
        "ROCKWOOL HardRock MultiFix DD", 
        "Foamglas T3+", 
        "EPS", 
        "XPS"
      ];
      
      if (mappedValues.includes(cleanedValue)) {
        return {
          label: cleanedValue,
          tooltip: "Standardized insulation type from product details",
          className: "font-semibold text-blue-600"
        };
      }
      break;
      
    case "Reason for Change":
      return {
        label: cleanedValue,
        className: cleanedValue === "Amendment" ? "font-semibold text-amber-600" : "font-semibold text-green-600"
      };
      
    case "Target U-Value":
    case "Target Min U-Value":
      if (cleanedValue !== "Not found") {
        return {
          label: cleanedValue,
          className: "font-mono"
        };
      }
      break;
  }

  return defaultFormat;
}
