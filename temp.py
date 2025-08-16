# from crewai.tools import tool
# from crewai import Agent, Task, Crew, LLM
# from e2b_code_interpreter import Sandbox
from dotenv import load_dotenv

# from crewai_tools import CodeInterpreterTool

# # Initialize the tool
# code_interpreter = CodeInterpreterTool(result_as_answer=True)

load_dotenv()

# # # Update tool definition using the decorator
# # @tool("Python Interpreter")
# # def execute_python(code: str) -> str:
# #     """
# #     Execute Python code and return the results.
# #     """
# #     with Sandbox() as sandbox:
# #         execution = sandbox.run_code(code)
# #         if execution is None:
# #             raise ValueError('Error unable to execute in E2B')
# #         if execution.text is None:
# #             return 'None'
# #         return execution.text

# # Define the agent
# python_executor = Agent(
#     role='Python Executor',
#     goal='Execute Python code and return the results',
#     backstory='You are an expert Python programmer capable of executing code and returning results.',
#     tools=[code_interpreter],
#     llm=LLM(model="gemini/gemini-2.5-flash")
# )

# # Define the task
# execute_task = Task(
#     description="""Scrape the list of highest grossing films from Wikipedia. It is at the URL:
# https://en.wikipedia.org/wiki/List_of_highest-grossing_films

# Answer the following questions and respond with a JSON array of strings containing the answer.

# 1. How many $2 bn movies were released before 2020?
# 2. Which is the earliest film that grossed over $1.5 bn?
# 3. What's the correlation between the Rank and Peak?
# 4. Draw a scatterplot of Rank and Peak along with a dotted red regression line through it.
#    Return as a base-64 encoded data URI, `"data:image/png;base64,iVBORw0KG..."` under 100,000 bytes.'""",
#     agent=python_executor,
#     expected_output="Return the output as a json array"
# )

# # Create the crew
# code_execution_crew = Crew(
#     agents=[python_executor],
#     tasks=[execute_task],
#     verbose=True,
# )

# # Run the crew
# result = code_execution_crew.kickoff()
# print(result)

import os

from e2b_code_interpreter import Sandbox
from google import genai
from google.genai import types
from pydantic import BaseModel


class GeneratedCode(BaseModel):
    code: str
    required_packages: list[str]


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_ai_code_gen(messages: list[str]):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=messages,
        config=types.GenerateContentConfig(
            # tools=[types.Tool(st)],
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            system_instruction="You're an expert in generating code for extracting and analyzing data using python. Just return the libraries needed (don't include any system libraries like json, base64 etc., since they will be preinstalled already) and the code (the result values only). The code you're generating should always return an json array as output (the array should contain answers to the questions only don't anything verbosely). Don't add any comments in the code that you're generating. You may get only one chance to run the code, so generate it with caution",
            response_mime_type="application/json",
            response_schema=GeneratedCode,
            temperature=0,
        ),
    )
    return response


if __name__ == "__main__":
    # messages = [
    #     """Scrape the list of highest grossing films from Wikipedia. It is at the URL:
    # https://en.wikipedia.org/wiki/List_of_highest-grossing_films

    # Answer the following questions and respond with a JSON array of strings containing the answer.

    # 1. How many $2 bn movies were released before 2020?
    # 2. Which is the earliest film that grossed over $1.5 bn?
    # 3. What's the correlation between the Rank and Peak?
    # 4. Draw a scatterplot of Rank and Peak along with a dotted red regression line through it.
    # Return as a base-64 encoded data URI, `"data:image/png;base64,iVBORw0KG..."` under 100,000 bytes.
    # Return the outputs as an json array for each question"""
    #             ]
    messages = [
        """The Indian high court judgement dataset contains judgements from the Indian High Courts, downloaded from [ecourts website](https://judgments.ecourts.gov.in/). It contains judgments of 25 high courts, along with raw metadata (as .json) and structured metadata (as .parquet).

- 25 high courts
- ~16M judgments
- ~1TB of data

Structure of the data in the bucket:

- `data/pdf/year=2025/court=xyz/bench=xyz/judgment1.pdf,judgment2.pdf`
- `metadata/json/year=2025/court=xyz/bench=xyz/judgment1.json,judgment2.json`
- `metadata/parquet/year=2025/court=xyz/bench=xyz/metadata.parquet`
- `metadata/tar/year=2025/court=xyz/bench=xyz/metadata.tar.gz`
- `data/tar/year=2025/court=xyz/bench=xyz/pdfs.tar`

This DuckDB query counts the number of decisions in the dataset.

```sql
INSTALL httpfs; LOAD httpfs;
INSTALL parquet; LOAD parquet;

SELECT COUNT(*) FROM read_parquet('s3://indian-high-court-judgments/metadata/parquet/year=*/court=*/bench=*/metadata.parquet?s3_region=ap-south-1');
```

Here are the columns in the data:

| Column                 | Type    | Description                    |
| ---------------------- | ------- | ------------------------------ |
| `court_code`           | VARCHAR | Court identifier (e.g., 33~10) |
| `title`                | VARCHAR | Case title and parties         |
| `description`          | VARCHAR | Case description               |
| `judge`                | VARCHAR | Presiding judge(s)             |
| `pdf_link`             | VARCHAR | Link to judgment PDF           |
| `cnr`                  | VARCHAR | Case Number Register           |
| `date_of_registration` | VARCHAR | Registration date              |
| `decision_date`        | DATE    | Date of judgment               |
| `disposal_nature`      | VARCHAR | Case outcome                   |
| `court`                | VARCHAR | Court name                     |
| `raw_html`             | VARCHAR | Original HTML content          |
| `bench`                | VARCHAR | Bench identifier               |
| `year`                 | BIGINT  | Year partition                 |

Here is a sample row:

```json
{
  "court_code": "33~10",
  "title": "CRL MP(MD)/4399/2023 of Vinoth Vs The Inspector of Police",
  "description": "No.4399 of 2023 BEFORE THE MADURAI BENCH OF MADRAS HIGH COURT ( Criminal Jurisdiction ) Thursday, ...",
  "judge": "HONOURABLE  MR JUSTICE G.K. ILANTHIRAIYAN",
  "pdf_link": "court/cnrorders/mdubench/orders/HCMD010287762023_1_2023-03-16.pdf",
  "cnr": "HCMD010287762023",
  "date_of_registration": "14-03-2023",
  "decision_date": "2023-03-16",
  "disposal_nature": "DISMISSED",
  "court": "33_10",
  "raw_html": "<button type='button' role='link'..",
  "bench": "mdubench",
  "year": 2023
}
```

Answer the following questions and respond with a JSON object containing the answer.

```json
{
  "Which high court disposed the most cases from 2019 - 2022?": "...",
  "What's the regression slope of the date_of_registration - decision_date by year in the court=33_10?": "...",
  "Plot the year and # of days of delay from the above question as a scatterplot with a regression line. Encode as a base64 data URI under 100,000 characters": "data:image/webp:base64,..."
}
```"""
    ]
    response = get_ai_code_gen(messages)
    if response.parsed is not None:
        generated_code: GeneratedCode = response.parsed
        print(generated_code.code)
        sbx = Sandbox(timeout=600)
        # with Sandbox() as sbx:/
        # for pkg in generated_code.required_packages:
        installation = sbx.commands.run(
            f"pip install {' '.join(generated_code.required_packages)} --ignore-installed"
        )
        print(installation)
        out = sbx.run_code(generated_code.code)
        print(out)
        i = 1
        while out.error:
            print(f"{i}: Iterating through the error")
            messages.append(str(out.error))
            response = get_ai_code_gen(messages)
            generated_code: GeneratedCode = response.parsed
            print(generated_code)
            sbx.commands.run(
                f"pip install {' '.join(generated_code.required_packages)}"
            )
            out = sbx.run_code(generated_code.code)
            print(out)
            if i >= 5:
                break
            i += 1
            print(out)
        sbx.kill()
