"""
Module `chatette.cli.interactive_commands.command_strategy`.
Contains the base class for all the commands that can be used with
the interactive mode, such that such a command will subclass this base class
in order to implement the strategy design pattern.
"""

import re

from chatette.utils import rchop
from chatette.parsing.parser_utils import UnitType
from chatette.cli.terminal_writer import TerminalWriter, RedirectionType


REDIRECTION_SYM = ">"
REDIRECTION_APPEND_SYM = ">>"

REGEX_SYM = '/'


class CommandStrategy(object):
    usage_str = "Undefined"  # Should be overriden by subclasses
    def __init__(self, command_str, quiet=False):
        self.command_tokens = CommandStrategy.tokenize(command_str)

        redirection_tuple = \
                CommandStrategy.find_redirection_file_path(self.command_tokens)
        if redirection_tuple is not None:
            self.remove_redirection_tokens()
            (redirection_type, redirection_filepath) = redirection_tuple
            self.print_wrapper = TerminalWriter(redirection_type,
                                                redirection_filepath)
        elif quiet:
            self.print_wrapper = \
                TerminalWriter(redirection_type=RedirectionType.quiet)
        else:
            self.print_wrapper = TerminalWriter(None)

        self._is_regex_global = None

    @staticmethod
    def tokenize(command_str):
        """Tokenizes a string that is a command."""
        splitted = command_str.split()
        if len(splitted) == 0:
            return []
        if len(splitted) == 1:
            return [splitted[0]]
        tokens = []
        current_token = ""
        inside_token = False
        for word in splitted:
            if inside_token:
                current_token += word + ' '
                if word.endswith('"') and (len(word) < 2 or word[-2] != '\\'):
                    inside_token = False
                    tokens.append(current_token.rstrip())
                    current_token = ""
            elif (    word.startswith('"') and word.endswith('"') \
                  and (len(word) < 2 or word[-2] != '\\')):
                tokens.append(word)
            elif word.startswith('"'):
                inside_token = True
                current_token += word + ' '
            else:  # not inside a token and not starting with "
                tokens.append(word)
        if current_token != "":
            tokens.append(current_token.rstrip())
        return tokens

    @staticmethod
    def find_redirection_file_path(tokens):
        """
        Finds the path of the file
        which the output of a command should be redirected to and
        returns it along with the type of redirection that it is (in a 2-tuple).
        The type of redirection is an enumeration item of type
        `RedirectionType`.
        Returns `None` if no redirection was found.
        Returns `(ignored, None)` if a redirection should be done to nowhere.
        (This can be achieved by using the redirections symbols and providing
        no filepath).
        """
        if len(tokens) < 3:
            return None
        if tokens[-2] == REDIRECTION_APPEND_SYM:
            return (RedirectionType.append, tokens[-1])
        if tokens[-2] == REDIRECTION_SYM:
            return (RedirectionType.truncate, tokens[-1])
        if (   tokens[-1] == REDIRECTION_APPEND_SYM
            or tokens[-1] == REDIRECTION_SYM):
            return (None, None)
        return None

    @staticmethod
    def get_unit_type_from_str(unit_type_str):
        """
        Transforms the string `unit_type_str`
        into the corresponding `UnitType` value.
        Returns `None` if there exist no corresponding `UnitType` value.
        """
        unit_type_str = unit_type_str.lower()
        if unit_type_str == "alias":
            return UnitType.alias
        if unit_type_str == "slot":
            return UnitType.slot
        if unit_type_str == "intent":
            return UnitType.intent
        return None

    @staticmethod
    def remove_quotes(text):
        """
        Remove the double quotes at the beginning and end of `text` and
        remove the escapement of other quotes.
        """
        return text[1:-1].replace(r'\"', '"')

    def get_name_as_regex(self, text):
        """
        If a regex is used within `text`,
        returns a compiled regex that is able to find all units with a name
        that matches some pattern.
        Returns `None` otherwise.
        """
        if text.startswith(REGEX_SYM) and (   text.endswith(REGEX_SYM)
                                           or text[-2] == REGEX_SYM
                                           or text[-3] == REGEX_SYM):
            splitted_str = [e for e in text.split(REGEX_SYM) if e != ""]
            if len(splitted_str) == 1:
                return re.compile(text[1:-1].replace('\\'+REGEX_SYM, REGEX_SYM))

            flags = splitted_str[-1]
            text_without_flags = rchop(text, flags)
            self._is_regex_global = 'g' in flags
            if 'i' in flags:
                return re.compile(text_without_flags[1:-1].replace('\\'+REGEX_SYM, REGEX_SYM),
                                    re.IGNORECASE)
            return re.compile(text_without_flags[1:-1].replace('\\'+REGEX_SYM, REGEX_SYM))
        return None

    def next_matching_unit_name(self, parser, unit_type, regex):
        """
        Yields the next unit name of type `unit_type`
        whose name matches `regex`.
        """
        if unit_type == UnitType.alias:
            relevant_dict = parser.alias_definitions
        elif unit_type == UnitType.slot:
            relevant_dict = parser.slot_definitions
        elif unit_type == UnitType.intent:
            relevant_dict = parser.intent_definitions
        else:
            raise ValueError("Unexpected unit type when matching regex: " +
                             str(unit_type))
        if self._is_regex_global:
            for unit_name in relevant_dict:
                if regex.search(unit_name):
                    yield unit_name
        else:
            for unit_name in relevant_dict:
                if regex.match(unit_name):
                    yield unit_name
    def get_all_matching_unit_name(self, parser, unit_type, regex):
        """
        Returns a list of unit names of type `unit_type`
        whose name matches `regex`.
        NOTE: this is used with 'delete' command since the generator that
              returns the same data cannot be used in that case (dict changes
              size during iteration).
        """
        if unit_type == UnitType.alias:
            relevant_dict = parser.alias_definitions
        elif unit_type == UnitType.slot:
            relevant_dict = parser.slot_definitions
        elif unit_type == UnitType.intent:
            relevant_dict = parser.intent_definitions
        else:
            raise ValueError("Unexpected unit type when matching regex: " +
                             str(unit_type))
        if self._is_regex_global:
            return [name for name in relevant_dict if regex.search(name)]
        return [name for name in relevant_dict if regex.match(name)]

    def remove_redirection_tokens(self):
        """
        Removes the tokens that represent a redirection
        from `self.command_tokens`.
        @pre: There are redirection tokens in the tokens.
        """
        if (   self.command_tokens[-2] == REDIRECTION_APPEND_SYM
            or self.command_tokens[-2] == REDIRECTION_SYM):
            self.command_tokens = self.command_tokens[:-2]
        else:
            self.command_tokens = self.command_tokens[:-1]


    def flush_output(self):
        """
        Asks the wrapper of print to flush its outputs
        to the redirected file (if such a file exists).
        """
        self.print_wrapper.flush()


    def should_exit(self):
        """
        Returns `True` if the program should exit the interactive mode.
        This method should be overriden by subclasses.
        """
        return False

    def execute(self, facade):
        """
        Executes the whole command represented by this object.
        `facade` is a facade to the whole system (contains links to the parser).
        This method can be overriden by subclasses if a different algorithm is
        required.
        """
        # TODO support variations
        if len(self.command_tokens) < 3:
            self.print_wrapper.error_log("Missing some arguments\nUsage: " +
                                         self.usage_str)
            return

        unit_type = CommandStrategy.get_unit_type_from_str(self.command_tokens[1])
        unit_regex = self.get_name_as_regex(self.command_tokens[2])
        if unit_regex is None:
            unit_name = CommandStrategy.remove_quotes(self.command_tokens[2])
            self.execute_on_unit(facade, unit_type, unit_name)
        else:
            count = 0
            for unit_name in self.next_matching_unit_name(facade.parser,
                                                          unit_type,
                                                          unit_regex):
                self.execute_on_unit(facade, unit_type, unit_name)
                count += 1
            if count == 0:
                self.print_wrapper.write("No " + unit_type.name + " matched.")
        self.finish_execution(facade)

    def execute_on_unit(self, facade, unit_type, unit_name):
        """
        Executes the command on a specific unit.
        This method HAS to be overriden by subclasses if they don't override
        `execute`.
        """
        raise NotImplementedError()

    def finish_execution(self, facade):
        """
        This function is executed at the end of the command and
        can be overriden to implement things such as cleaning up or changing
        the size of dictionaries and list that were being iterated over.
        NOTE: it is called no matter what happened before (the command worked
              or failed).
        """
        pass
