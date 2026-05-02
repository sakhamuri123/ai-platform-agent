import boto3
import subprocess
import time
import os, requests

client = boto3.client("bedrock-runtime", region_name="ap-south-1")

def generate_backend_config(env='dev', service='network'):
    return f"""
  terraform {{
      backend "s3" {{
          bucket = "rajesh-platform-tf-state"
          key  = "{env}/{service}/terraform.tfstate"
          region = "ap-south-1"
          dynamodb_table = "terraform-locks"
          encrypt = true
      }}
  }}
  """
  
def ask_llm(prompt):
    response = client.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        
                        "text": prompt
                    }
                ]
            }
        ],
        inferenceConfig={
            "maxTokens": 1000,
            "temperature": 0.3
        }
    )

    return response["output"]["message"]["content"][0]["text"]

def generate_terraform():
    prompt = """
Generate ONLY Terraform resource blocks for AWS infrastructure.

1. AWS VPC
2. Public subnet
3. Private subnet
4. Internet gateway
5. Route tables

STRICT RULES:

- Return only raw terraform code
- No explanations
- No markdowns
- No ``` blocks
- No introductory text
- Do not include terraform block 
- Do not include provider block
- Only resource definitions
"""

    return ask_llm(prompt)

def clean_output(tf_code):
    # Remove any unwanted characters or formatting from the LLM output
    tf_code = tf_code.replace("```hcl", "")
    tf_code = tf_code.replace("```", "")
    tf_code = tf_code.replace("Here's the Terraform code for the resources you requested:", "")
    
    return tf_code.strip()

def write_to_file(terraform_code, env='dev', service='network'):
    backend = generate_backend_config(env, service)
    
    full_code = f"""
    provider "aws" {{
        region = "ap-south-1"
    }}
    
    {backend}
    
    {terraform_code}
    """
    
    with open("main.tf", "w") as f:
        f.write(full_code.strip())
        
        print("\nTerraform code with backend written to main.tf")


    
    
def validate_terraform():
    try:
        print("\nRunning terraform format...")
        subprocess.run(["terraform", "fmt"], check=True)
        
        print("\nRunning terraform init ...")
        subprocess.run(["terraform", "init", "-reconfigure"], check=True)
        
        print("\nRunning terraform validate ...")
        subprocess.run(["terraform", "validate"], check=True, capture_output=True, text=True)
        
        print("\nTerraform validation successfull")
        
        return True, None
        
    except subprocess.CalledProcessError as e: 
         print(f"Error during terraform validation:")
         return False, e.stderr
     
     
def terraform_plan():
    try:
        print(f"\nRunning terraform plan ...")
        
        result = subprocess.run(
            ["terraform", "plan"],
            check=True,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        return True, result.stdout
    
    except subprocess.CalledProcessError as e:
        print(f"Error during terraform plan:")
        
        return False, e.stderr

def push_to_github():
    try:
        print("\nPushing code to github..")
        
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "AI generated terraform infrastructure"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        print("\nCode pushed successfully to github")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nGithub push failed.")
        return False
    
def push_feature_branch():
    branch_name = f"ai-generated-{int(time.time())}"
    try:
        print(f"\nCreating branch: {branch_name}")
        
        subprocess.run(
            ["git", "checkout", "-b", branch_name], check=True
            )
        
        subprocess.run(
            ["git", "add", "."], check=True
            )
        
        subprocess.run(
            ["git", "commit", "-m", "AI generated terraform infrastructure"], check=True
        )
        
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name], check=True
        )    
        
        print(f"\nFeature branch pushed successfully")
       
        return True, branch_name
   
    except subprocess.CalledProcessError:
        print(f"\nBranch push failed.")
        return False, None


def create_pull_request(branch_name):
    token = os.getenv("GITHUB_TOKEN")

    repo_owner = "sakhamuri123"
    repo_name = "ai-platform-agent"

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    payload = {
        "title": "AI Generated Infrastructure Change",
        "head": branch_name,
        "base": "main",
        "body": "This PR was automatically created by AI infrastructure agent."
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    if response.status_code == 201:
        print("\nPull Request created successfully!")
        print(response.json()["html_url"])
        return True
    else:
        print("\nPR creation failed")
        print(response.text)
        return False
    

         
        

def fix_terraform_code(original_code, error_message):
    prompt = f"""
    The following terraform code failed validation:
    
    {original_code}
    
    terraform_error:
    
    {error_message}
    
    Fix the terraform code:
    
    Rules:
    - Return only raw terraform code
    - No markdowns
    - No explanations
    - No ``` blocks
    """
    
    return ask_llm(prompt)

# Main flow the code generation, validation, and github workflow
         
if __name__ == "__main__":
    tf_code = generate_terraform()
    
    max_retries = 3
    
    for attempt in range(max_retries):
        print(f"\nAttempt {attempt + 1} of {max_retries}")
        
        # Step 1: Clean LLM output
        cleaned_code = clean_output(tf_code)
        
        # Step 2: Write Terraform file
        write_to_file(cleaned_code,env='dev', service='network')
        
        # Step 3: Validate Terraform
        success, error = validate_terraform()
        
        if success:
            print("\nTerraform code is valid!")
            
            # step 4: Terraforrm plan
            plan_success, plan_output = terraform_plan()
            
            if plan_success:
                print("\n Terraform plan successfull!")
                
                # Step 5: Create feature branch + push
                branch_success, branch_name = push_feature_branch()
                
                if branch_success:
                   print(f"\nBranch {branch_name} created and code pushed successfully!")
                   
                   #step6: create pull request 
                   pr_success = create_pull_request(branch_name)
                  
                   if pr_success:
                       print(f"\nGitops workflow completed successfully")
                       break
                   else:
                       print(f"\nPR creation failed")
                       break
                else:
                    print(f"\n Feature branch push failed")
                    break    
                    
            else:
                print("\n Terraform plan failed")
                break
            
        print("\nAgent attempting self-healing...")
        tf_code = fix_terraform_code(cleaned_code, error)
        
    else:
        print("\nFailed to generate valid Terraform code after multiple attempts.")
    
    
    
    
   