package de.medizininformatikinitiative.sq2cql.cli;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import de.numcodex.sq2cql.Translator;
import de.numcodex.sq2cql.model.Mapping;
import de.numcodex.sq2cql.model.MappingContext;
import de.numcodex.sq2cql.model.MappingTreeBase;
import de.numcodex.sq2cql.model.MappingTreeModuleRoot;
import de.numcodex.sq2cql.model.structured_query.StructuredQuery;
import org.apache.commons.cli.*;
import org.apache.commons.cli.help.HelpFormatter;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.Map;

public class Main {

    private static final ObjectMapper JSON_UTIL = new ObjectMapper();

    private static final String INPUT_SQ_ARG_NAME = "INPUT_SQ_FILE";
    private static final String OUTPUT_CQL_ARG_NAME = "OUTPUT_CQL_FILE";
    private static final String CL_SYNTAX = "<command> [OPTS] <%s> [<%s>]".formatted(INPUT_SQ_ARG_NAME, OUTPUT_CQL_ARG_NAME);

    private static final Option HELP_OPTION = Option.builder()
            .option("h")
            .longOpt("help")
            .desc("Prints this message")
            .hasArg(false)
            .required(false)
            .get();
    private static final Options CLI_OPTIONS = getCliOptions();

    private static Options getCliOptions() {
        return new Options()
                .addOption(HELP_OPTION)
                .addOption(Option.builder()
                        .option("cm")
                        .longOpt("cql-mapping")
                        .desc("Path to CQL mapping file")
                        .hasArg()
                        .argName("FILE")
                        .required()
                        .converter((String path) ->
                                Stream.of(JSON_UTIL.readValue(Path.of(path).toFile(), Mapping[].class))
                                        .collect(Collectors.toMap(Mapping::key, Function.identity(), (a, b) -> a)))
                        .get()
                ).addOption(Option.builder()
                        .option("ct")
                        .longOpt("concept-tree")
                        .desc("Path to concept tree file")
                        .hasArg()
                        .argName("FILE")
                        .required()
                        .converter((String path) ->
                                new MappingTreeBase(Arrays.stream(JSON_UTIL.readValue(Path.of(path).toFile(), MappingTreeModuleRoot[].class)).toList()))
                        .get()
                ).addOption(Option.builder()
                        .option("csa")
                        .longOpt("code-system-aliases")
                        .desc("(Optional) Path to code system aliases file")
                        .hasArg()
                        .argName("FILE")
                        .converter((String path) ->
                                JSON_UTIL.readValue(Path.of(path).toFile(), new TypeReference<HashMap<String, String>>() {
                                }))
                        .get()
                );
    }

    private static Optional<CommandLine> getCliArgs(String[] args) {
        var parser = new DefaultParser();
        try {
            var clOptions = parser.parse(CLI_OPTIONS, args);
            return Optional.of(clOptions);
        } catch (ParseException exc) {
            System.err.println(exc.getMessage());
            printHelpMessage();
            return Optional.empty();
        }
    }

    private static File getInputSQFile(CommandLine commandLine) throws ParseException {
        var args = commandLine.getArgs();
        if (args.length == 0)
            throw new ParseException("Missing required positional argument %s".formatted(INPUT_SQ_ARG_NAME));
        else return new File(args[0]);
    }

    private static Optional<File> getOutputCQLFile(CommandLine commandLine) {
        var args = commandLine.getArgs();
        return args.length >= 2 ?
                Optional.of(new File(args[1]))
                :
                Optional.empty();
    }

    private static boolean helpOption(String[] args) {
        try {
            var options = new Options().addOption(HELP_OPTION);
            return new DefaultParser().parse(options, args, true).hasOption("h");
        } catch (ParseException exc) {
            throw new RuntimeException("Failed to parse args", exc);
        }
    }

    private static void printHelpMessage() {
        try {
            HelpFormatter.builder().get().printHelp(CL_SYNTAX, null, CLI_OPTIONS, null, false);
        } catch (IOException ioeExc) {
            throw new RuntimeException("Failed to print help message", ioeExc);
        }
    }

    public static void main(String[] args) {
        if (helpOption(args)) printHelpMessage();
        else getCliArgs(args).ifPresentOrElse(
                (clArgs) -> {
                    try {
                        var sqFile = getInputSQFile(clArgs);
                        var cqlFile = getOutputCQLFile(clArgs);
                        var translator = Translator.of(MappingContext.of(
                                clArgs.getParsedOptionValue("cm"),
                                clArgs.getParsedOptionValue("ct"),
                                clArgs.getParsedOptionValue("csa", Map::of)
                        ));

                        var result = translator.toCql(JSON_UTIL.readValue(sqFile, StructuredQuery.class)).print();

                        cqlFile.ifPresentOrElse(
                                file -> {
                                    try (BufferedWriter writer = new BufferedWriter(new FileWriter(file))) {
                                        writer.write(result);
                                    } catch (IOException exc) {
                                        throw new RuntimeException("Failed to write to output file", exc);
                                    }
                                },
                                () -> System.out.println(result)
                        );
                    } catch (Exception exc) {
                        System.err.printf("Translation failed: %s%n", exc.getMessage());
                        System.exit(1);
                    }
                },
                () -> System.exit(1)
        );
    }

}
