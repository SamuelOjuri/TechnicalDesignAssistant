export interface ParameterFormatting {
  label: string;
  tooltip?: string;
  className?: string;
}

export function getParameterFormatting(key: string, value: string): ParameterFormatting {
  // Default formatting
  const defaultFormat: ParameterFormatting = {
    label: value,
  };

  switch (key) {
    case "Post Code":
      if (value.length <= 2 && value !== "Not found" && value !== "Not provided") {
        return {
          label: value,
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
      
      if (mappedValues.includes(value)) {
        return {
          label: value,
          tooltip: "Standardized insulation type from product details",
          className: "font-semibold text-blue-600"
        };
      }
      break;
      
    case "Reason for Change":
      return {
        label: value,
        className: value === "Amendment" ? "font-semibold text-amber-600" : "font-semibold text-green-600"
      };
      
    case "Target U-Value":
    case "Target Min U-Value":
      if (value !== "Not found") {
        return {
          label: value,
          className: "font-mono"
        };
      }
      break;
  }

  return defaultFormat;
}
