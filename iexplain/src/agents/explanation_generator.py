from autogen import ConversableAgent

class ExplanationGeneratorAgent(ConversableAgent):
    def __init__(self, name="ExplanationGenerator", system_message="I am the Explanation Generator Agent. I generate explanations for the tracked events.", **kwargs):
        # Initialize with the name and system message, along with other configurations
        super().__init__(name=name, system_message=system_message, **kwargs)

    def generate_explanation(self, tracked_event):
        """Generate a human-understandable explanation for a tracked event.
        
        Args:
            tracked_event (dict): A dictionary containing the details of the event to explain.

        Returns:
            str: A string containing the generated explanation.
        """
        # Example: Simple explanation logic, can be replaced with complex reasoning
        event_type = tracked_event.get("event_type", "an event")
        timestamp = tracked_event.get("timestamp", "some time")
        details = tracked_event.get("details", {})
        
        # Generate explanation string based on event details
        explanation = f"At {timestamp}, {event_type} occurred with details: {details}."
        return explanation

    def generate_reply(self, msg):
        """Override this method to handle incoming messages and generate explanations."""
        if msg.get('role') == 'system' and msg.get('content') == 'generate_explanation':
            tracked_event = msg.get('event', {})
            explanation = self.generate_explanation(tracked_event)
            return {"role": "system", "content": explanation}
        
        # If the message is something else, you can add additional conditions here
        return super().generate_reply(msg)  # Default to the base class behavior

    def is_termination_msg(self, msg):
        """Override if you want to define specific termination criteria."""
        # For this agent, you might want to stop if it receives a specific signal
        return False

if __name__ == "__main__":
    # Example instantiation
    explanation_generator = ExplanationGeneratorAgent()

    # Simulating generating an explanation for a tracked event
    tracked_event = {
        "event_type": "AI_Action",
        "timestamp": "2024-08-21T10:05:00Z",
        "details": {"action": "move", "direction": "north"}
    }
    explanation = explanation_generator.generate_explanation(tracked_event)
    print(explanation)

