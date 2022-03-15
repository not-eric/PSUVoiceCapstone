# Privacy Policy Browser
# Credit:  Josiah Baldwin, Eric Dale, Ethan Fleming, Jacob Hilt,
#          Darian Hutchinson, Joshua Lund, Bennett Wright
#
# The alexa skill is implemented as a collection of handlers for certain types of user input.
# This is paired with a S3 bucket that is holding data about location & acceptance in privacy policy.
# These are paired together to implement a kind of state machine.
#
# The components of the privacy policy are handled in the privacy_policy module, go there for more info.

import logging
import ask_sdk_core.utils as ask_utils
import sys
import os
sys.path.append(os.path.dirname(__file__))

from ask_sdk_s3.adapter import S3Adapter
s3_adapter = S3Adapter(bucket_name=os.environ["S3_PERSISTENCE_BUCKET"])

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.ui import PlayBehavior, Reprompt, SsmlOutputSpeech, PlainTextOutputSpeech

from ask_sdk_model import Response, IntentRequest, Intent, Slot, SlotConfirmationStatus
from privacy_policy import PrivacyPolicy

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

policy = PrivacyPolicy("policy.xml")
max_section_num = len(policy.sections)
repeat = False
cont = False
quit = False

persistent_variables = {
    "lastSectionRead": -1,
    "acceptedSections": policy.accepted_sections
}

def load_attributes(handler_input):
    """Load persistent variables from S3 storage."""
    attributes_manager = handler_input.attributes_manager
    persistent_variables = handler_input.attributes_manager.persistent_attributes

def save_attributes(handler_input):
    """Save persistent variables to S3 storage."""
    attributes_manager = handler_input.attributes_manager
    attributes_manager.persistent_attributes = persistent_variables
    attributes_manager.save_persistent_attributes()

def create_section_response(handler_input, section_number):
    """Return a response object that reads the specified section number."""
    if section_number >= max_section_num:
        return (
            handler_input.response_builder
                .speak("The end of the policy was reached.")
                .ask("Would you like to accept the policy?")
                .response
        )
    
    section = policy.sections[section_number]
    
    persistent_variables["lastSectionRead"] = section_number
    
    speak_output = 'Starting from section {num}'.format(num = section_number + 1)
    speak_output += ". " + section.all_atoms_as_string()
    speak_output += "To accept or decline this section of the policy, say accept or decline. Otherwise, say continue."
    
    return (
        handler_input.response_builder
            .speak(speak_output)
            .ask("Would you like to continue reading the next section?  To do so, say continue.")
            .response
    )

def have_read_section():
    """Return true if a section was previously read."""
    return persistent_variables["lastSectionRead"] >= 0

def list_accepted_sections():
    """Return a string stating which sections of the policy have been read."""
    count = 0
    speak_output = ""
    
    for i in range(len(policy.accepted_sections)):
        if policy.is_section_accepted(i):
            if count == 0:
                speak_output += ": "
            else:
                speak_output += ", "
            count += 1
            speak_output += str(i + 1)
    
    if count == len(policy.accepted_sections):
        return "You have accepted all sections of this policy."
    
    elif count == 1:
        return "You have accepted section" + speak_output + "."
    
    elif count > 0:
        return "You have accepted sections" + speak_output + "."
    
    else:
        return "You have not accepted any sections in this policy."

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler run when the skill first launches."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        """Return a response object that plays at launch."""
        
        # Maybe we should change up this opening dialog to something like:
        # 
        # "Welcome to the privacy policy reader. I can read through privacy policies and keep track 
        # of which sections you would like to accept or decline. Say, 'list options' to hear all that I can do for you,
        # or say, 'Start from the beginning' to start reading."
        # 
        # This might make it sound less overwhelming on startup - Darian
        speak_output = "Welcome to the privacy policy reader. Here are some things I can do for you: 1. list options, " \
        + "2. hear the table of contents, " \
        + "3. Start from the beginning, " \
        + "4. start from section by saying the word section followed by the desired section number," \
        + "5. 'skip section' or 'continue', " \
        + "6. 'repeat that', " \
        + "7. 'accept or decline section' optionally followed by the section number, " \
        + "8. 'read accepted sections', " \
        + "or 'quit.'"
        
        load_attributes(handler_input)
        
        if persistent_variables["lastSectionRead"] >= 0:
            speak_output = "Welcome back to the privacy policy reader. To continue from where you left off say continue, " \
            + "or to hear other options say 1, help, or menu."
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


# OUR CODE #################################################################################################

def get_toc_string():
    """Return a string stating the top-level titles of the privacy policy."""
    titles = "Here are the Privacy Policy section titles"
    i = 1
    for title in policy.section_titles:
        titles += f". {i}. " + str(title).rstrip(".")
        i += 1
    
    return titles

class TableOfContentsHandler(AbstractRequestHandler):
    """Handler run when the user requests the table of contents."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("TableOfContents")(handler_input)

    def handle(self, handler_input):
        """Return a response object that plays the table of contents."""

        return (
            handler_input.response_builder
                .speak(get_toc_string())
                .ask("What would you like to do?")
                .response
        )


class ReadAcceptedHandler(AbstractRequestHandler):
    """Handler run when the user requests a list of accepted sections."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("readAccepted")(handler_input)

    def handle(self, handler_input):
        """Return a response object that plays a list of accepted sections."""
        
        load_attributes(handler_input)
        speak_output = list_accepted_sections()
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("What would you like to do?")
                .response
        )


class ListOptionsHandler(AbstractRequestHandler):
    """Handler run when the user requests help or menu options."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("ListOptions")(handler_input) or ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        """Return a response object that plays a list of menu options."""
        
        speak_output = "OK, you can tell me " \
        + "1. 'menu' to listen to this menu, " \
        + "2. 'table of contents', " \
        + "3. 'read from beginning', " \
        + "4. 'read section' followed by the section number, " \
        + "5. 'skip section' or 'continue', " \
        + "6. 'repeat that', " \
        + "7. 'accept or decline section' optionally followed by the section number, " \
        + "8. 'read accepted sections', " \
        + "or 'quit.'"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("What would you like to do?")
                .response
        )


class ResetHandler(AbstractRequestHandler):
    """Debug handle to reset AWS slots
       Invoke with "Erase all data" """
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("Reset")(handler_input)

    def handle(self, handler_input):
        """Delete persistent variables and return a response object that
           reports success."""
        
        policy.decline_all_sections()
        persistent_variables["lastSectionRead"] = -1
        persistent_variables["acceptedSections"] = policy.accepted_sections
        
        response = "Okay, I've forgotten everything.  What was my name again?"
        
        save_attributes(handler_input)
        
        return (
            handler_input.response_builder
                .speak(response)
                .ask("What would you like to do?")
                .response
        )


class StartFromSectionHandler(AbstractRequestHandler):
    """Handler run when the user asks to start from a section."""
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("StartFromSection")(handler_input)

    def handle(self, handler_input):
        """Update the last section read variable and return a response object
           that plays the requested section."""
        load_attributes(handler_input)
        
        slots = handler_input.request_envelope.request.intent.slots
        num = int(slots["num"].value) - 1
        
        response = create_section_response(handler_input, num)
        
        save_attributes(handler_input)
        
        return response


class AcceptPolicyHandler(AbstractRequestHandler):
    """Handler run when the user asks to accept a section of the policy."""
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("AcceptPolicy")(handler_input)

    def handle(self, handler_input):
        """Update the accepted sections variable and return a response object
           that reports success or failure."""
        
        load_attributes(handler_input)
        
        slots = handler_input.request_envelope.request.intent.slots
        user_acceptence = slots["userAcceptence"].value
        
        speak_output = ""
        
        if slots["acceptNum"].value:
            num = int(slots["acceptNum"].value) - 1
        elif slots["acceptWhat"].value:
            num = -1
        else:
            if not have_read_section():
                return (
                    handler_input.response_builder
                        .speak("Sorry, you haven't read any sections yet.")
                        .ask("What would you like to do?")
                        .response
                )
            num = persistent_variables["lastSectionRead"]
        
        policy.set_accepted_sections(persistent_variables["acceptedSections"])
        
        if user_acceptence == "accept":
            
            if num >= 0:
                policy.accept_section(num)
                speak_output += "Ok. Section " + str(num + 1) + " has been accepted."
            
            else:
                policy.accept_all_sections()
                speak_output += "Ok. All sections of the policy have been accepted."
        
        elif user_acceptence == "decline":
            
            if num >= 0:
                policy.decline_section(num)
                speak_output += "Ok. Section " + str(num + 1) + " has been declined."
            
            else:
                policy.decline_all_sections()
                speak_output += "Ok. All sections of the policy have been declined."
        
        persistent_variables["acceptedSections"] = policy.accepted_sections
        save_attributes(handler_input)
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class StartFromBeginningHandler(AbstractRequestHandler):
    """Handler run when the user asks to start reading from the beginning the
       policy."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("StartFromBeginning")(handler_input)

    def handle(self, handler_input):
        """Update the last section read variable and return a response object
           that plays the first section of the policy."""
        
        load_attributes(handler_input)
        response = create_section_response(handler_input, 0)
        save_attributes(handler_input)
        
        return response


# can we have 'next section' call this handler as well?
class ContinueHandler(AbstractRequestHandler):
    """Handler run when the user asks to continue reading the next section
       of the policy."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("Continue")(handler_input)

    def handle(self, handler_input):
        """Update the last section read variable and return a response object
           that plays the next section of the policy."""
        load_attributes(handler_input)
        
        persistent_variables["lastSectionRead"] += 1
        num = persistent_variables["lastSectionRead"]
        
        response = create_section_response(handler_input, num)
        
        save_attributes(handler_input)
        
        return response


# INTENTS TO BE CALLED WHILE READING:


class RepeatWhileReadingHandler(AbstractRequestHandler):
    """Handler run when the user asks to repeat the current section of the
       policy."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("RepeatWhileReading")(handler_input)

    def handle(self, handler_input):
        """Return a response object that plays the current section of the
           policy or reports failure if no section has been read."""
        load_attributes(handler_input)
        
        if not have_read_section():
            return (
                handler_input.response_builder
                    .speak("Sorry, I'm not sure which section you want me to repeat.")
                    .ask("What would you like to do?")
                    .response
            )
        
        num = persistent_variables["lastSectionRead"]
        
        return create_section_response(handler_input, num)


# PREGEN CODE #################################################################################################


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Handler run when the user asks to cancel the skill."""
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        """Return a response object that plays a goodbye message and leaves the
           skill."""
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class FallbackIntentHandler(AbstractRequestHandler):
    """Handler run when the user issues a command we don't handle."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        """Return a response object that reports we don't understand that
           command, and await further commands."""
        
        logger.info("In FallbackIntentHandler")
        speech = "Hmm, I'm not sure. You can say Hello or Help. What would you like to do?"
        reprompt = "I didn't catch that. What can I help you with?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler run when the session ends."""
    
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        """Return a blank response object that terminates the session."""

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and
       debugging.  It will simply repeat the intent the user said. You can
       create custom handlers for your intents by defining them above, then
       also adding them to the request handler chain below."""
    def can_handle(self, handler_input):
        """Return true if this handler can handle the specified handler
           input."""
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        """Return a response object reporting the intent that was triggered."""
        
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you
       receive an error stating the request handler chain is not found, you
       have not implemented a handler for the intent being invoked or included
       it in the skill builder below."""
    def can_handle(self, handler_input, exception):
        """Return true if this handler can handle the specified handler
           input."""
        return True

    def handle(self, handler_input, exception):
        """Log an error and return a response object indicating an error
           occurred."""
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# END PREGEN CODE #################################################################################################

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.

sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

sb.add_request_handler(LaunchRequestHandler())
# OUR INTENTS
sb.add_request_handler(ListOptionsHandler())
sb.add_request_handler(TableOfContentsHandler())
sb.add_request_handler(ReadAcceptedHandler())

sb.add_request_handler(StartFromSectionHandler())
sb.add_request_handler(StartFromBeginningHandler())
sb.add_request_handler(ContinueHandler())
sb.add_request_handler(ResetHandler())

# READING INTENTS
sb.add_request_handler(AcceptPolicyHandler())
sb.add_request_handler(RepeatWhileReadingHandler())

# OUR INTENTS ^
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
