#!/usr/bin/env python3
"""
Script to create a comprehensive Nibav FAQ with warranty information
"""

import pandas as pd
import os

def create_nibav_faq():
    """Create a comprehensive Nibav FAQ with warranty information"""
    
    # Comprehensive Nibav FAQ data
    faq_data = [
        # Warranty Information
        ["What is the warranty period for Nibav lifts?", 
         "Nibav lifts come with a 2-year comprehensive warranty covering all mechanical and electrical components.",
         "Nibav lifts come with a 2-year comprehensive warranty covering all mechanical and electrical components. This includes the motor, control system, safety mechanisms, and structural components. Extended warranty options are available for up to 5 years."],
        
        ["What does the warranty cover?", 
         "The warranty covers all mechanical and electrical components including motor, control system, and safety mechanisms.",
         "The warranty covers all mechanical and electrical components including the motor, control system, safety mechanisms, structural components, and installation defects. It does not cover damage from misuse, accidents, or normal wear and tear."],
        
        ["How long is the warranty valid?", 
         "Standard warranty is 2 years from the date of installation.",
         "The standard warranty is valid for 2 years from the date of installation. Extended warranty plans are available for 3, 4, or 5 years. Warranty registration must be completed within 30 days of installation."],
        
        ["What is not covered under warranty?", 
         "Damage from misuse, accidents, normal wear and tear, and unauthorized modifications are not covered.",
         "The warranty does not cover damage from misuse, accidents, normal wear and tear, unauthorized modifications, improper maintenance, or damage caused by external factors like power surges or natural disasters."],
        
        ["How do I claim warranty service?", 
         "Contact Nibav customer service with your warranty registration number and description of the issue.",
         "To claim warranty service, contact Nibav customer service at 1-800-NIBAV or email support@nibav.com. Provide your warranty registration number, installation date, and detailed description of the issue. A service technician will be dispatched within 48 hours."],
        
        # Product Information
        ["What is a Nibav lift?", 
         "Nibav lifts are residential elevators designed for homes, providing safe and convenient vertical transportation.",
         "Nibav lifts are residential elevators specifically designed for homes. They provide safe, convenient, and stylish vertical transportation solutions for multi-story residences. They are compact, energy-efficient, and can be installed in existing homes with minimal structural modifications."],
        
        ["How much weight can a Nibav lift carry?", 
         "Nibav lifts can carry up to 500 pounds (227 kg) safely.",
         "Nibav lifts are designed to safely carry up to 500 pounds (227 kg), which is sufficient for most residential use including wheelchairs, mobility scooters, and multiple passengers. The lift includes safety mechanisms to prevent overloading."],
        
        ["What are the dimensions of a Nibav lift?", 
         "Standard Nibav lifts have a footprint of 3' x 4' and require a minimum ceiling height of 8'.",
         "Standard Nibav lifts have a compact footprint of 3 feet by 4 feet (91cm x 122cm) and require a minimum ceiling height of 8 feet (244cm). Custom sizes are available for specific requirements. The lift can be installed in closets, stairwells, or dedicated shafts."],
        
        ["How fast does a Nibav lift travel?", 
         "Nibav lifts travel at a safe speed of 0.3 feet per second (9cm/s).",
         "Nibav lifts travel at a safe and comfortable speed of 0.3 feet per second (9cm/s). This speed is optimized for residential use, providing a smooth ride while ensuring safety. The lift can travel between floors in approximately 10-15 seconds depending on floor height."],
        
        # Installation
        ["How long does installation take?", 
         "Professional installation typically takes 1-2 days depending on the complexity.",
         "Professional installation of a Nibav lift typically takes 1-2 days depending on the complexity of the installation and any required structural modifications. The process includes site preparation, lift assembly, electrical connection, testing, and safety certification."],
        
        ["What are the installation requirements?", 
         "Requires a dedicated space, electrical connection, and structural support for the lift mechanism.",
         "Installation requires a dedicated space with proper dimensions, a 120V electrical connection, structural support for the lift mechanism, and compliance with local building codes. The installation site must be accessible for delivery and assembly."],
        
        ["Can Nibav lifts be installed in existing homes?", 
         "Yes, Nibav lifts can be retrofitted into existing homes with minimal structural modifications.",
         "Yes, Nibav lifts are specifically designed for retrofitting into existing homes. They require minimal structural modifications and can be installed in closets, stairwells, or dedicated spaces. A professional assessment is conducted to ensure compatibility and safety."],
        
        # Maintenance
        ["How often should I maintain my Nibav lift?", 
         "Annual professional maintenance is recommended to ensure optimal performance and safety.",
         "Annual professional maintenance is recommended to ensure optimal performance and safety. This includes inspection of mechanical components, electrical systems, safety mechanisms, and cleaning. Regular maintenance helps prevent issues and extends the lifespan of your lift."],
        
        ["What maintenance is required?", 
         "Regular cleaning, lubrication of moving parts, and annual professional inspection.",
         "Maintenance includes regular cleaning of the lift car and tracks, lubrication of moving parts, inspection of safety mechanisms, testing of emergency systems, and electrical system checks. Professional maintenance should be performed annually by certified technicians."],
        
        ["Can I perform maintenance myself?", 
         "Basic cleaning can be done by homeowners, but professional maintenance is required for technical components.",
         "Basic cleaning and visual inspections can be performed by homeowners. However, technical maintenance including electrical work, mechanical adjustments, and safety system testing must be performed by certified Nibav technicians to ensure safety and maintain warranty coverage."],
        
        # Safety
        ["What safety features does a Nibav lift have?", 
         "Multiple safety features including emergency stop, overload protection, and backup power system.",
         "Nibav lifts include multiple safety features: emergency stop button, overload protection, backup power system, safety interlocks, emergency lowering mechanism, and automatic door sensors. All lifts meet or exceed safety standards for residential elevators."],
        
        ["What happens during a power outage?", 
         "The backup power system allows safe operation and emergency lowering during power outages.",
         "Nibav lifts are equipped with a backup power system that allows safe operation during power outages. The system can power the lift for emergency use and includes an emergency lowering mechanism to safely return passengers to ground level if needed."],
        
        ["Is a Nibav lift safe for children?", 
         "Yes, with proper supervision and safety features, Nibav lifts are safe for children.",
         "Yes, Nibav lifts are safe for children when used with proper supervision. Safety features include door sensors, emergency stop buttons, and smooth operation. Children should be supervised when using the lift, and safety instructions should be provided."],
        
        # Cost and Financing
        ["How much does a Nibav lift cost?", 
         "Nibav lifts typically cost between $25,000 to $45,000 depending on configuration and installation requirements.",
         "Nibav lifts typically cost between $25,000 to $45,000 depending on the model, configuration, installation requirements, and any necessary structural modifications. This includes the lift unit, installation, electrical work, and initial safety certification."],
        
        ["Is financing available for Nibav lifts?", 
         "Yes, Nibav offers various financing options including monthly payment plans and medical financing.",
         "Yes, Nibav offers various financing options to make lifts more accessible. These include monthly payment plans, medical financing programs, and partnerships with healthcare financing companies. Payment terms typically range from 12 to 84 months with competitive interest rates."],
        
        ["Are there any tax benefits for installing a Nibav lift?", 
         "Medical tax deductions may be available if the lift is prescribed by a healthcare provider.",
         "Medical tax deductions may be available if the lift is prescribed by a healthcare provider as medically necessary. This can include deductions for the lift cost, installation, and related expenses. Consult with a tax professional for specific eligibility requirements."]
    ]
    
    # Create DataFrame
    df = pd.DataFrame(faq_data, columns=["Question", "Concise Answer (bot default)", 'Details if user asks "Tell me more"'])
    
    # Save to CSV
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    csv_path = os.path.join(data_dir, "Nibav_FAQ_comprehensive.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"✅ Created comprehensive Nibav FAQ with {len(faq_data)} entries")
    print(f"📁 Saved to: {csv_path}")
    
    # Show sample
    print("\n📝 Sample entries:")
    for i, row in df.head(3).iterrows():
        print(f"  {i+1}. Q: {row['Question']}")
        print(f"     A: {row['Concise Answer (bot default)']}")

if __name__ == "__main__":
    create_nibav_faq() 