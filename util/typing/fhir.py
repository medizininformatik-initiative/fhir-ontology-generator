from typing import Annotated

FHIRPathlike = Annotated[str, ("FHIRPath-like expression that might contain placeholders or other markers transformed "
                               "during later processing to obtain a valid FHIRPath expression")]

FHIRPath = Annotated[FHIRPathlike, "Valid FHIRPath expression"]