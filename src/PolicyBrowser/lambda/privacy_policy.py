import xmltodict
import itertools

# Classes used for representing & accessing privacy policy data.
#
# ## Example Usage:
#
# Create privacy policy object
# > policy = PrivacyPolicy("policy.xml")
#
# Print top level section titles (table of contents)
# > for title in policy.section_titles:
# >    print(title)
#
# Print all section names (including policy title and subsections)
# > for title in policy.all_titles:
# >    print(title)
#
# Print subsection names in an indexed section
# > for title in policy.sections[2].section_titles:
#    print(title)
#
# Print subsection names in a named section
# > for title in policy.title_map["Collection of Your Personal Information and Other Information"].section_titles:
# >    print(title)
#
# Figure out where to stop reading given a start point
# > start_reading_index = policy.title_map["Information Provided Directly to Us."].atom_index
# > stop_reading_index = policy.get_read_last_index(start_reading_index)
#
# Print atoms that we will read starting from that start point
# > while start_reading_index <= stop_reading_index:
# >    print(policy.all_atoms[start_reading_index])
# >    start_reading_index += 1


class PrivacyPolicyAtom:
    """Represent a title or paragraph within a policy."""
    
    def __init__(self, parent_section, text, atom_index):
        """Construct an atom with the specified parent section, text contents
           and index within the policy."""
        self.__parent_section = parent_section
        self.__text = text
        self.__atom_index = atom_index

    @property
    def parent_section(self):
        """Return the parent section of this atom."""
        return self.__parent_section

    def has_as_parent(self, parent_section):
        """Return true if this atom is part of the given parent section."""
        if parent_section is self.__parent_section:
            return True
        if self.__parent_section is None:
            return False
        return self.__parent_section.has_as_parent(parent_section)

    @property
    def text(self):
        """Return the text contents of this atom."""
        return self.__text

    @property
    def atom_index(self):
        """Return the index of this atom within the policy."""
        return self.__atom_index

    def __repr__(self):
        """Return the text contents of this atom."""
        return self.__text


class PrivacyPolicyTitle(PrivacyPolicyAtom):
    """Represent a title within a policy."""

    def __init__(self, parent_section, text, atom_index):
        """Construct a title with the specified parent section, text contents
           and index within the policy."""
        super().__init__(parent_section, text, atom_index)


class PrivacyPolicyParagraph(PrivacyPolicyAtom):
    """Represent a paragraph within a policy."""

    def __init__(self, parent_section, text, atom_index):
        """Construct a paragraph with the specified parent section, text
           contents and index within the policy."""
        super().__init__(parent_section, text, atom_index)


class PrivacyPolicySection:
    """Represent a root section, section or subsection within a policy."""
    
    def __init__(self, parent_section, section_dict, starting_index):
        """Construct a policy section and its child sections/atoms with the
           specified parent and starting index.  Uses section_dict dictionary
           dumped by xmltodict from policy XML file."""
        title = section_dict.get("title")
        if title:
            self.__title = PrivacyPolicyTitle(self, title, starting_index)
            starting_index += 1
        else:
            self.__title = None

        self.__parent_section = parent_section
        self.__paragraphs = []
        self.__subsections = []

        paragraphs = section_dict.get("paragraph")

        if isinstance(paragraphs, list):
            for paragraph in paragraphs:
                self.__paragraphs.append(PrivacyPolicyParagraph(self, paragraph, starting_index))
                starting_index += 1
        elif paragraphs is not None:
            self.__paragraphs.append(PrivacyPolicyParagraph(self, paragraphs, starting_index))
            starting_index += 1

        subsections = section_dict.get("subsection") or section_dict.get("section")

        if isinstance(subsections, list):
            for subsection in subsections:
                sub_obj = PrivacyPolicySection(self, subsection, starting_index)
                self.__subsections.append(sub_obj)
                starting_index += len(sub_obj.all_atoms)

        elif subsections is not None:
            sub_obj = PrivacyPolicySection(self, subsections, starting_index)
            self.__subsections.append(sub_obj)
            starting_index += len(sub_obj.all_atoms)

        self.__all_atoms = []
        self.__all_titles = []
        self.__dump_all_atoms(self.__all_atoms, self.__all_titles)

        self.__subsection_titles = []
        for subsection in self.__subsections:
            subsection_title = subsection.title
            if subsection_title:
                self.__subsection_titles.append(subsection_title)

    @property
    def title(self):
        """Return the title atom for this section."""
        return self.__title

    @property
    def parent_section(self):
        """Return the parent section of this section (or None if this is the
           root section of the policy)."""
        return self.__parent_section

    @property
    def paragraphs(self):
        """Return the paragraphs contained directly within this section."""
        return self.__paragraphs

    @property
    def subsections(self):
        """Return the sections contained directly within this section."""
        return self.__subsections

    @property
    def all_atoms(self):
        """Return all titles/paragraphs contained within this section and its
           child sections."""
        return self.__all_atoms
    
    def all_atoms_as_string(self):
        """Return all titles/paragraphs contained within this section and its
           child sections as a string."""
        string = ""
        for atom in self.all_atoms:
            atom = str(atom).rstrip(".")
            string += f"{atom}. "
        return string

    @property
    def all_titles(self):
        """Return all titles contained within this section and its child
           sections."""
        return self.__all_titles

    @property
    def subsection_titles(self):
        """Return the titles of this section's direct child sections."""
        return self.__subsection_titles

    def has_as_parent(self, parent_section):
        """Return true if this section is part of the given parent section."""
        if parent_section is self.__parent_section:
            return True
        if not self.__parent_section:
            return False
        return self.__parent_section.has_as_parent(parent_section)

    def __dump_all_atoms(self, all_atoms, all_titles):
        """Dumps all titles and atoms contained within this section and its
           child sections into the specified lists."""
        if self.__title:
            all_titles.append(self.__title)
            all_atoms.append(self.__title)
        all_atoms.extend(self.__paragraphs)
        for subsection in self.__subsections:
            subsection.__dump_all_atoms(all_atoms, all_titles)


class PrivacyPolicy:
    """Represent a policy."""

    def __init__(self, file):
        """Construct a policy object from the given XML file path."""
        file = open(file, "r")
        policy_dict = xmltodict.parse(file.read())["policy"]
        file.close()

        self.__root_section = PrivacyPolicySection(None, policy_dict, 0)
        self.__date = policy_dict["date"]
        self.__url = policy_dict["url"]

        self.__title_map = dict(zip(map(lambda title: title.text, self.__root_section.all_titles), self.__root_section.all_titles))
        self.__accepted_sections = list(itertools.repeat(False, len(self.sections)))
    
    @property
    def accepted_sections(self):
        """Return a list of booleans indicating whether the top-level sections
           within this policy have been accepted."""
        return self.__accepted_sections
    
    def is_section_accepted(self, num):
        """Return true if the specified section number has been accepted."""
        return self.__accepted_sections[num]
    
    def accept_section(self, num):
        """Set the specified section number to accepted."""
        self.__accepted_sections[num] = True
    
    def decline_section(self, num):
        """Set the specified section number to declined."""
        self.__accepted_sections[num] = False
    
    def accept_all_sections(self):
        """Set all sections in the policy to accepted."""
        for i in range(len(self.__accepted_sections)):
            self.__accepted_sections[i] = True
    
    def decline_all_sections(self):
        """Set all sections in the policy to declined."""
        for i in range(len(self.__accepted_sections)):
            self.__accepted_sections[i] = False
    
    def is_policy_accepted(self):
        """Return true if all sections in the policy have been accepted."""
        all_accepted = True
        for section_accepted in self.__accepted_sections:
            if not section_accepted:
                all_accepted = False
                break
        return all_accepted
    
    def set_accepted_sections(self, accepted_sections):
        """Set the accepted sections to the given list of booleans."""
        for i in range(len(self.__accepted_sections)):
            self.__accepted_sections[i] = True if accepted_sections[i] else False
    
    @property
    def root_section(self):
        """Return the root section of this policy."""
        return self.__root_section

    @property
    def date(self):
        """Return the date string of this policy."""
        return self.__date

    @property
    def url(self):
        """Return the URL of this policy."""
        return self.__url

    @property
    def title(self):
        """Return a list of the title atom of this policy."""
        """Convenience property for accessing self.root_section.title."""
        return self.__root_section.title

    @property
    def sections(self):
        """Return a list of the top-level sections of this policy."""
        """Convenience property for accessing self.root_section.subsections."""
        return self.__root_section.subsections

    @property
    def all_atoms(self):
        """Return a list of all titles/paragraphs contained within this
           policy."""
        """Convenience property for accessing self.root_section.all_atoms."""
        return self.__root_section.all_atoms

    @property
    def all_titles(self):
        """Return a list of all titles contained within this policy (including
           the policy's own title and all subsection titles."""
        """Convenience property for accessing self.root_section.all_titles."""
        return self.__root_section.all_titles

    @property
    def section_titles(self):
        """Return a list of top-level titles contained within this policy."""
        """Convenience property for accessing
           self.root_section.subsection_titles."""
        return self.__root_section.subsection_titles

    @property
    def title_map(self):
        """Return a map containing top-level section title strings as keys and
           title atoms as values."""
        """Would be useful for looking up policy elements given their titles."""
        return self.__title_map

    def get_read_last_index(self, read_start_index):
        """Return the index of the last atom contained within the section or
           subsection that contains the atom with the specified index."""
        """Would be useful for jumping to a specific paragraph in the policy
           and determining where reading should stop."""
        all_atoms = self.__root_section.all_atoms
        section = all_atoms[read_start_index].parent_section

        while True:
            read_start_index += 1
            if not ((read_start_index < len(all_atoms)) and all_atoms[read_start_index].has_as_parent(section)):
                break

        return read_start_index - 1
