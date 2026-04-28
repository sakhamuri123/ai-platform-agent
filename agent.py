import boto3
import subprocess

client = boto3.client("bedrock-runtime", region_name="ap-south-1")

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
Generate production-ready Terraform code in ap-south-1 region for:

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
"""

    return ask_llm(prompt)

def clean_output(tf_code):
    # Remove any unwanted characters or formatting from the LLM output
    tf_code = tf_code.replace("```hcl", "")
    tf_code = tf_code.replace("```", "")
    tf_code = tf_code.replace("Here's the Terraform code for the resources you requested:", "")
    
    return tf_code.strip()

def write_to_file(terraform_code):
    filename = "main.tf"
    with open(filename, "w") as f:
        f.write(terraform_code)
    print(f"Terraform code saved to {filename}")


    
    
def validate_terraform():
    try:
        print("\nRunning terraform format...")
        subprocess.run(["terraform", "fmt"], check=True)
        
        print("\nRunning terraform init ...")
        subprocess.run(["terraform", "init"], check=True)
        
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
         
if __name__ == "__main__":
    tf_code = generate_terraform()
    
    max_retries = 3
    
    for attempt in range(max_retries):
        print(f"\nAttempt {attempt + 1} of {max_retries}")
        
        cleaned_code = clean_output(tf_code)
        write_to_file(cleaned_code)
        
        success, error = validate_terraform()
        
        if success:
            print("\nTerraform code is valid!")
            
            plan_success, plan_output = terraform_plan()
            
            if plan_success:
                print("\n Terraform plan successfull!")
                git_success = push_to_github()
                
                if git_Success:
                    print("\nInfrastructure code successfully pushed to github")
                else:
                    print("\nFailed to push code to github")
                break
            else:
                print("\n Terraform plan failed")
                break
            
        print("\nAgent attempting self-healing...")
        tf_code = fix_terraform_code(cleaned_code, error)
        
    else:
        print("\nFailed to generate valid Terraform code after multiple attempts.")
    
    
    
    
   