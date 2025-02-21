from typing import Annotated

FHIRPath = Annotated[str, "FHIRPath expression"]

FHIRPathlike = Annotated[str, ("FHIRPath-like expression that might contain placeholders or other markers transformed "
                               "during later processing to obtain a valid FHIRPath expression")]