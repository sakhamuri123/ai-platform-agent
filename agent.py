import boto3
import subprocess
import time
import os, requests, re

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
Generate ONLY Terraform resource blocks for AWS infrastructure only in ap-south-1 region.

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
- DO NOT hardcode availability zones
- Use data.aws_availability_zones for AZ selection
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
            ["terraform", "plan", "-no-color"],
            check=True,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        return True, result.stdout
    
    except subprocess.CalledProcessError as e:
        print(f"Error during terraform plan:")
        
        return False, e.stderr
    
# Analyzing the plan for risk analysis could be an additional step here where we parse the plan output and look for any destructive changes. For simplicity, we are skipping that step in this implementation.

def analyze_plan(plan_output):
    analysis = {
        "add": 0,
        "change": 0,
        "destroy": 0,
        "risk": "LOW",
        "warnings": []
    }
    # Extract summary line from the plan output
    
    # case 1: Normal plan with changes
    # Plan: 6 to add, 0 to change, 0 to destroy.
    
    match = re.search(r"Plan:\s+(\d+)\s+to add,\s+(\d+)\s+to change,\s+(\d+)\s+to destroy", plan_output, re.IGNORECASE | re.MULTILINE)
    if match:
        analysis["add"] = int(match.group(1))
        analysis["change"] = int(match.group(2))
        analysis["destroy"] = int(match.group(3))
        
    # case 2: No changes
    # No changes. Infrastructure is up-to-date.
    elif "No changes" in plan_output:
        analysis["add"] = 0
        analysis["change"] = 0
        analysis["destroy"] = 0 
        analysis["warnings"].append("No changes detected in terraform plan.")
        
    else:
        print("\nDEBUG: Plan line not found in output") 
        
               

    # Simple risk analysis based on the number of changes
    if analysis["destroy"] > 0:
        analysis["risk"] = "High"
        analysis["warnings"].append("Destructive changes detected!")
        
    if analysis["change"] > 5:
        analysis["risk"] = "Medium"
        analysis["warnings"].append("Large infrastructure modification detected, More than 5 changes detected, review recommended.")
        
    if analysis["add"] > 10:
        analysis["risk"] = "Medium"
        analysis["warnings"].append("Larged infrastructure deployment detected.")
    
    # Basic cost awreness
    
    if "aws_nat_gateway" in plan_output:
        analysis["warnings"].append("NAT Gateway detected (high cost)")
        
    if "0.0.0.0/0" in plan_output:
        analysis["warnings"].append("Open access detected (0.0.0.0/0)")
        
    return analysis

# Generate human redable summary of the plan analysis to be included in the PR description

def generate_summary(analysis):
    #Input: analysis (dictionary from analyze_plan)
    summary = f"""
    ### AI Infrastructure Analysis

    - Resources to add: {analysis["add"]}
    - Resources to change: {analysis["change"]}
    - Resources to destroy: {analysis["destroy"]}
    - Risk level: {analysis["risk"]}
     """
    if analysis["warnings"]:
       summary += "\n\n ## warnings: \n"
       for w in analysis["warnings"]:
           summary += f"- {w}\n"
           
    return summary

# defining tfsec for any potential security issues in the code could be an additional step here.

def run_tfsec():
    try:
        print("\nRunning tfsec security scan..")
        
        result = subprocess.run(
            ["tfsec", ".", "--no-color"],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        return result.stdout
    
    except Exception as e:
        print(f"\nError running tfsec: {e}")
        return ""
    
# Analyzing tfsec output for security issues could be an additional step here where we parse the tfsec output and look for any critical issues.
def analyze_tfsec(tfsec_output):
    policy = {
        "block": False,
        "warnings": [],
        "details": []
    }
    if "CRITICAL" in tfsec_output:
        policy["block"] = True
        policy["warnings"].append("Critical security issues detected by tfsec!")
    if "HIGH" in tfsec_output:
        policy["warnings"].append("High severity security issues detected by tfsec!")
    if "MEDIUM" in tfsec_output:
        policy["warnings"].append("Medium severity security issues detected by tfsec!")
    if "0.0.0.0/0" in tfsec_output:
        policy["warnings"].append("Open access detected in security scan")
    return policy  
    

# Cost detection function could be an additional step here where we parse the plan output and look for any high cost resources like NAT gateways, RDS instances, etc.

def analyze_cost(plan_output):
    cost_warnings = []
    
    if "aws_nat_gateway" in plan_output:
        cost_warnings.append("NAT Gateway detected (high cost) (~$30-50/month + data charges)")
    
    if "aws_lb" in plan_output or "aws_alb" in plan_output:
        cost_warnings.append("Load Balancer detected (potential cost) (hourly + data cost)")
    
    if "aws_instance" in plan_output:
        cost_warnings.append("EC2 instance detected (potential cost depends on instance type)")
        
        
    if "aws_db_instance" in plan_output:
        cost_warnings.append("RDS instance detected (potentially high cost)")
        
    return cost_warnings

def approval_decision(analysis, policy):
    if policy["block"]:
        return "BLOCK, Policy violation detected. PR creation blocked."
    if analysis["risk"] == "High":
        return "Manual approval required"
    if analysis["risk"] == "Medium":
        return "Review recommended"
    
    return "Auto-approved"
    

           

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


def create_pull_request(branch_name,analysis,security_analysis,cost_warnings,decision):
    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        print("\nGITHUB_TOKEN not found in environment variables.")
        return False

    repo_owner = "sakhamuri123"
    repo_name = "ai-platform-agent"

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    
    
    summary = generate_summary(analysis)
    
    
    # Security and policy findings
    
    if security_analysis["warnings"]:
        summary += "\n\n## Security Findings from tfsec:\n"
        for f in security_analysis["warnings"]:
            summary += f"- {f}\n"
            
    if cost_warnings:
        summary += "\n\n## Cost Warnings:\n"
        for c in cost_warnings:
            summary += f"- {c}\n"
    
    # approval decision into summary
    summary += f"""\n\n #Approval decision
              - {decision}\n
              """
              
    

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    payload = {
        "title": "AI Generated Infrastructure Change",
        "head": branch_name,
        "base": "main",
        "body": summary
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
                
                # Analyze plan BEFORE pushing code
                analysis = analyze_plan(plan_output)
                print(f"""
                ================ AI Decision Summary ================

                Resources to Add    : {analysis['add']}
                Resources to Change : {analysis['change']}
                Resources to Destroy: {analysis['destroy']}
                Risk Level          : {analysis['risk']}

                ====================================================
             """)
                
                # Skip PR and push branch if there are no changes.
                
                if analysis["add"] == 0 and analysis["change"] == 0 and analysis["destroy"] == 0:
                    print("\nNo changes detected in terraform plan. Skipping PR creation.")
                    break  
                
                tfsec_output = run_tfsec()
                
                security_analysis = analyze_tfsec(tfsec_output)
                
                cost_warnings = analyze_cost(plan_output)
                
                # policy enforcement - block PR creation if critical issues are detected by tfsec
                if security_analysis["block"]:
                    print("\nPolicy violation detected. Blocking PR creation.")
                    print(f"\nreasons")
                    for w in security_analysis["warnings"]:
                        print(f"- {w}")
                    break 
                # Add approval gate and logic
                decision = approval_decision(analysis, security_analysis)
                print(f"""
                 ================ Approval Decision ================

                 Decision : {decision}

                ===================================================
                  """)
                
                # Step 5: Create feature branch + push
                branch_success, branch_name = push_feature_branch()
                
                if branch_success:
                   print(f"\nBranch {branch_name} created and code pushed successfully!")
                   
                   #step6: create pull request 
                   pr_success = create_pull_request(branch_name,analysis,security_analysis,cost_warnings,decision)
                  
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
    
    
    
    
   