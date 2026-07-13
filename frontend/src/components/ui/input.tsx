import * as React from "react";
import { cn } from "../../lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-[#c9c9c4] bg-white px-3 py-2 text-sm text-[#171717] ring-offset-white transition-[border-color,box-shadow] file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[#8a8b8d] focus-visible:border-[#b82c25] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b82c25]/20 disabled:cursor-not-allowed disabled:bg-[#f4f4f1] disabled:opacity-60",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input }; 